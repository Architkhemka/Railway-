"""Unit and HTTP contract tests for the Phase 2 prediction services."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from services.delay_prediction.app import create_app as create_delay_app
from services.delay_prediction.model import train_model as train_delay
from services.fare_prediction.app import create_app as create_fare_app
from services.fare_prediction.model import train_models as train_fare_models
from services.ticket_confirmation.app import create_app as create_ticket_app
from services.ticket_confirmation.model import train_model as train_ticket


def _classifier(input_size: int = 4) -> RandomForestClassifier:
    features = np.asarray(
        [
            [0, position, days, travel_class]
            for position in range(1, 11)
            for days in (2, 30)
            for travel_class in range(5)
        ],
        dtype=float,
    )
    if input_size == 5:
        features = np.column_stack((features, np.ones(len(features))))
    labels = np.asarray([int(row[1] < 6 and (row[0] == 1 or row[2] > 10)) for row in features])
    model = RandomForestClassifier(n_estimators=8, max_depth=4, random_state=11)
    model.fit(features, labels)
    return model


def _regressor(input_size: int, output_size: int = 1) -> RandomForestRegressor:
    features = np.arange(1, 101, dtype=float).reshape(20, 5)[:, :input_size]
    if output_size == 1:
        targets: Any = features[:, 0] * 2.0 + features[:, -1]
    else:
        targets = np.column_stack((features[:, 0] * 2.0, features[:, 1] + 2, features[:, 2] / 10))
    model = RandomForestRegressor(n_estimators=8, max_depth=4, random_state=13)
    model.fit(features, targets)
    return model


def _audit_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_ticket_prediction_api_returns_confidence_shap_and_metrics(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(audit_path))
    app = create_ticket_app(_classifier(), "test-7")

    with TestClient(app) as client:
        response = client.post(
            "/v1/ticket/predict",
            json={
                "ticket_status": "WL",
                "waitlist_position": 5,
                "days_until_departure": 20,
                "travel_class": "3A",
            },
        )
        assert client.get("/health").json() == {"status": "healthy", "model_version": "test-7"}
        assert "railway_predictions_total" in client.get("/metrics").text

    assert response.status_code == 200
    body = response.json()
    assert 0 <= body["confirmation_probability"] <= 1
    assert body["final_berth_status"] in {"WL", "RAC", "CNF"}
    assert 0 <= body["confidence"] <= 1
    assert body["model_version"] == "test-7"
    assert body["explanation"][0]["feature"]
    assert _audit_events(audit_path)[0]["event"] == "prediction_completed"


def test_ticket_api_rejects_invalid_travel_class() -> None:
    with TestClient(create_ticket_app(_classifier())) as client:
        response = client.post(
            "/v1/ticket/predict",
            json={
                "ticket_status": "WL",
                "waitlist_position": 5,
                "days_until_departure": 20,
                "travel_class": "XX",
            },
        )
    assert response.status_code == 422


def test_delay_prediction_api_returns_disruption_alert_and_explanation(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "delay.jsonl"))
    app = create_delay_app(_regressor(3, 3), "delay-2")

    with TestClient(app) as client:
        response = client.post(
            "/v1/delay/predict",
            json={
                "train_number": "SYN-101",
                "station_code": "PUNE",
                "historical_delay_minutes": 45,
                "observation_hour": 12,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["arrival_delay_minutes"] >= 0
    assert body["departure_delay_minutes"] >= 0
    assert 0 <= body["station_congestion"] <= 1
    assert body["proactive_alerts"]
    assert body["alternative_options"]
    assert 0 <= body["confidence"] <= 1
    assert body["model_version"] == "delay-2"
    assert body["explanation"][0]["effect"] in {"increases", "decreases"}


def test_fare_prediction_api_returns_booking_window_and_shap(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "fare.jsonl"))
    fare_model = _regressor(5)
    surge_model = _classifier(input_size=5)
    app = create_fare_app(fare_model, surge_model, {"fare": "3", "surge": "2"})

    with TestClient(app) as client:
        response = client.post(
            "/v1/fare/predict",
            json={
                "travel_class": "3A",
                "base_fare": 980,
                "current_fare": 1_050,
                "demand_index": 0.9,
                "days_until_departure": 5,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["forecast_fare"] >= 0
    assert 0 <= body["demand_surge_probability"] <= 1
    assert body["optimal_booking_window"] in {"book_now", "monitor", "wait"}
    assert 0 <= body["confidence"] <= 1
    assert body["model_versions"] == {"fare": "3", "surge": "2"}
    assert body["explanation"]


def test_training_functions_register_seeded_models(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "training-audit.jsonl"))
    for train in (train_ticket, train_delay, train_fare_models):
        with pytest.raises(ValueError, match="at least 100 synthetic rows"):
            train(99)

    registrations: list[tuple[str, int]] = []

    def register(
        model: Any,
        *,
        model_name: str,
        service_name: str,
        dataset_name: str,
        row_count: int,
        metrics: dict[str, float],
    ) -> str:
        assert model_name.startswith("railway-")
        assert service_name in {"ticket_confirmation", "delay_prediction", "fare_prediction"}
        assert dataset_name
        assert metrics
        registrations.append((model_name, row_count))
        return f"run-{len(registrations)}"

    monkeypatch.setattr("services.ticket_confirmation.model.log_and_register_model", register)
    monkeypatch.setattr("services.delay_prediction.model.log_and_register_model", register)
    monkeypatch.setattr("services.fare_prediction.model.log_and_register_model", register)

    assert train_ticket(160) == "run-1"
    assert train_delay(160) == "run-2"
    assert train_fare_models(160) == ("run-3", "run-4")
    assert len(registrations) == 4
    assert all(count > 50 for _, count in registrations)
    assert all(
        row["event"] == "model_registered"
        for row in _audit_events(tmp_path / "training-audit.jsonl")
    )
