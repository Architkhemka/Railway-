"""Training and inference logic for ticket confirmation probabilities."""

from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

from railway_ai_platform.data.generators import GenerationOptions
from railway_ai_platform.data.loader import SyntheticDataLoader
from railway_ai_platform.ml.audit import record_audit_event
from railway_ai_platform.ml.explainability import explain_prediction
from railway_ai_platform.ml.tracking import log_and_register_model

SERVICE = "ticket_confirmation"
MODEL_NAME = "railway-ticket-confirmation"
FEATURE_NAMES = ["ticket_status", "waitlist_position", "days_until_departure", "travel_class"]
_STATUS_CODE = {"WL": 0.0, "RAC": 1.0}
_CLASS_CODE = {"SL": 0.0, "3A": 1.0, "2A": 2.0, "1A": 3.0, "CC": 4.0}


def ticket_features(
    ticket_status: str,
    waitlist_position: int,
    days_until_departure: int,
    travel_class: str,
) -> list[float]:
    """Encode ticket inputs in the stable order used to train the classifier."""
    return [
        _STATUS_CODE[ticket_status],
        float(waitlist_position),
        float(days_until_departure),
        _CLASS_CODE[travel_class],
    ]


def train_model(count: int = 1_200) -> str:
    """Train from generated booking/cancellation trends and register the classifier."""
    if count < 100:
        raise ValueError("ticket confirmation training requires at least 100 synthetic rows")
    loader = SyntheticDataLoader(GenerationOptions(count=count, seed=42))
    bookings = loader.load("bookings")
    cancellations = loader.load("cancellations")
    cancellation_rates = {
        status: sum(
            row["status_at_cancellation"] == status and row["seats_released"] is True
            for row in cancellations
        )
        / max(1, sum(row["status_at_cancellation"] == status for row in cancellations))
        for status in _STATUS_CODE
    }
    features: list[list[float]] = []
    labels: list[int] = []
    for index, booking in enumerate(bookings):
        status = str(booking["status"])
        if status not in _STATUS_CODE:
            continue
        position = int(booking["waitlist_position"] or 1)
        booked_at = str(booking["booked_at"])
        booked_day = int(booked_at[8:10])
        lead_days = 120 - (index * 37 % 120)
        days_until = max(1, min(120, lead_days - booked_day % 7))
        travel_class = str(booking["travel_class"])
        chance = (
            0.16
            + cancellation_rates[status] * 0.52
            + (0.19 if status == "RAC" else 0.0)
            + np.exp(-position / (16 if status == "WL" else 7)) * 0.26
            + min(days_until, 60) * 0.002
            + _CLASS_CODE[travel_class] * 0.006
        )
        chance = float(np.clip(chance, 0.03, 0.97))
        features.append(ticket_features(status, position, days_until, travel_class))
        labels.append(int((index * 7919 % 10_007) / 10_007 < chance))

    matrix = np.asarray(features, dtype=float)
    target = np.asarray(labels, dtype=int)
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=9,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(matrix, target)
    score = float(accuracy_score(target, model.predict(matrix)))
    run_id = log_and_register_model(
        model,
        model_name=MODEL_NAME,
        service_name=SERVICE,
        dataset_name="synthetic bookings and cancellations",
        row_count=len(target),
        metrics={"training_accuracy": score},
    )
    record_audit_event(
        SERVICE,
        "model_registered",
        {"model": MODEL_NAME, "run_id": run_id, "training_rows": len(target)},
    )
    return run_id


def predict_ticket(model: Any, features: list[float]) -> dict[str, Any]:
    """Return confirmation probability, inferred berth status, confidence and SHAP."""
    probability = float(model.predict_proba(np.asarray([features]))[0][1])
    if probability >= 0.55:
        berth_status = "CNF"
    elif probability >= 0.3:
        berth_status = "RAC"
    else:
        berth_status = "WL"
    confidence = max(probability, 1.0 - probability)
    return {
        "confirmation_probability": round(probability, 4),
        "final_berth_status": berth_status,
        "confidence": round(confidence, 4),
        "explanation": explain_prediction(model, features, FEATURE_NAMES, output_index=1),
    }
