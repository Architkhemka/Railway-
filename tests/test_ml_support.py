"""Tests for shared MLflow, SHAP, and audit helpers."""

import hashlib
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from railway_ai_platform.ml.audit import record_audit_event
from railway_ai_platform.ml.tracking import (
    load_latest_registered_model,
    log_and_register_model,
    tracking_uri,
)


def test_tracking_uri_uses_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow.test:5000")
    assert tracking_uri() == "http://mlflow.test:5000"
    monkeypatch.delenv("MLFLOW_TRACKING_URI")
    assert tracking_uri() == "http://localhost:5000"


def test_log_and_register_model_logs_metrics_and_returns_run_id() -> None:
    run = MagicMock()
    run.info.run_id = "run-42"
    with (
        patch("railway_ai_platform.ml.tracking.mlflow.set_tracking_uri") as set_uri,
        patch("railway_ai_platform.ml.tracking.mlflow.set_experiment") as set_experiment,
        patch("railway_ai_platform.ml.tracking.mlflow.start_run") as start_run,
        patch("railway_ai_platform.ml.tracking.mlflow.log_params") as log_params,
        patch("railway_ai_platform.ml.tracking.mlflow.log_metrics") as log_metrics,
        patch("railway_ai_platform.ml.tracking.mlflow.sklearn.log_model") as log_model,
    ):
        start_run.return_value.__enter__.return_value = run
        result = log_and_register_model(
            object(),
            model_name="test-model",
            service_name="test",
            dataset_name="synthetic",
            row_count=100,
            metrics={"mae": 1.25},
        )

    assert result == "run-42"
    set_uri.assert_called_once_with("http://localhost:5000")
    set_experiment.assert_called_once_with("railway-test")
    log_params.assert_called_once()
    log_metrics.assert_called_once_with({"mae": 1.25})
    log_model.assert_called_once()


def test_load_latest_model_selects_highest_version() -> None:
    model = object()
    with (
        patch("railway_ai_platform.ml.tracking.MlflowClient") as client_class,
        patch(
            "railway_ai_platform.ml.tracking.mlflow.sklearn.load_model",
            return_value=model,
        ) as load_model,
    ):
        client_class.return_value.search_model_versions.return_value = [
            SimpleNamespace(version="1"),
            SimpleNamespace(version="4"),
            SimpleNamespace(version="2"),
        ]
        loaded, version = load_latest_registered_model("test-model")

    assert loaded is model
    assert version == "4"
    load_model.assert_called_once_with("models:/test-model/4")


def test_load_latest_model_fails_explicitly_when_registry_is_empty() -> None:
    with patch("railway_ai_platform.ml.tracking.MlflowClient") as client_class:
        client_class.return_value.search_model_versions.return_value = []
        with pytest.raises(RuntimeError, match="no registered MLflow model"):
            load_latest_registered_model("missing-model")


def test_audit_events_are_hash_chained_and_verifiable(
    monkeypatch: Any,
    tmp_path: Any,
) -> None:
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("AUDIT_LOG_PATH", str(path))
    record_audit_event("ticket", "model_loaded", {"model_version": "1"})
    record_audit_event("ticket", "prediction_completed", {"confidence": 0.8})
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert len(records) == 2
    assert records[0]["previous_hash"] == "0" * 64
    assert records[1]["previous_hash"] == records[0]["event_hash"]
    for record in records:
        event_hash = record.pop("event_hash")
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
        assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == event_hash
