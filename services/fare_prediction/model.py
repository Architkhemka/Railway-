"""Training and inference logic for fare movement and demand surges."""

from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error

from railway_ai_platform.data.generators import GenerationOptions
from railway_ai_platform.data.loader import SyntheticDataLoader
from railway_ai_platform.ml.audit import record_audit_event
from railway_ai_platform.ml.explainability import explain_prediction, regression_confidence
from railway_ai_platform.ml.tracking import log_and_register_model

SERVICE = "fare_prediction"
FARE_MODEL_NAME = "railway-fare-forecast"
SURGE_MODEL_NAME = "railway-fare-demand-surge"
FEATURE_NAMES = [
    "base_fare",
    "current_fare",
    "demand_index",
    "days_until_departure",
    "travel_class",
]
_CLASS_CODE = {"SL": 0.0, "3A": 1.0, "2A": 2.0, "1A": 3.0, "CC": 4.0}


def fare_features(
    base_fare: float,
    current_fare: float,
    demand_index: float,
    days_until_departure: int,
    travel_class: str,
) -> list[float]:
    """Encode fare request fields in training feature order."""
    return [
        base_fare,
        current_fare,
        demand_index,
        float(days_until_departure),
        _CLASS_CODE[travel_class],
    ]


def train_models(count: int = 1_200) -> tuple[str, str]:
    """Train and register separate fare forecast and demand surge models."""
    if count < 100:
        raise ValueError("fare prediction training requires at least 100 synthetic rows")
    rows = SyntheticDataLoader(GenerationOptions(count=count, seed=42)).load("fares")
    features: list[list[float]] = []
    forecast_targets: list[float] = []
    surge_targets: list[int] = []
    for index, row in enumerate(rows):
        base_fare = float(row["base_fare"] or 0)
        fare = float(row["fare_amount"] or 0)
        demand = float(row["demand_index"] or 0)
        travel_class = str(row["travel_class"])
        days = 1 + index * 37 % 120
        features.append(fare_features(base_fare, fare, demand, days, travel_class))
        uplift = max(0.0, demand - 0.65) * 0.16 + max(0, 30 - days) * 0.0015
        forecast_targets.append(fare * (1.0 + uplift))
        surge_targets.append(int(demand >= 0.8))

    matrix = np.asarray(features, dtype=float)
    fare_target = np.asarray(forecast_targets, dtype=float)
    surge_target = np.asarray(surge_targets, dtype=int)
    fare_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    fare_model.fit(matrix, fare_target)
    fare_error = float(mean_absolute_error(fare_target, fare_model.predict(matrix)))
    fare_run = log_and_register_model(
        fare_model,
        model_name=FARE_MODEL_NAME,
        service_name=SERVICE,
        dataset_name="synthetic fares",
        row_count=len(fare_target),
        metrics={"forecast_training_mae": fare_error},
    )
    record_audit_event(
        SERVICE,
        "model_registered",
        {"model": FARE_MODEL_NAME, "run_id": fare_run, "training_rows": len(fare_target)},
    )

    surge_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    surge_model.fit(matrix, surge_target)
    surge_accuracy = float(accuracy_score(surge_target, surge_model.predict(matrix)))
    surge_run = log_and_register_model(
        surge_model,
        model_name=SURGE_MODEL_NAME,
        service_name=SERVICE,
        dataset_name="synthetic fares",
        row_count=len(surge_target),
        metrics={"surge_training_accuracy": surge_accuracy},
    )
    record_audit_event(
        SERVICE,
        "model_registered",
        {"model": SURGE_MODEL_NAME, "run_id": surge_run, "training_rows": len(surge_target)},
    )
    return fare_run, surge_run


def predict_fare(
    fare_model: Any,
    surge_model: Any,
    features: list[float],
) -> dict[str, Any]:
    """Forecast fare and demand, recommend booking timing, and explain the estimate."""
    row = np.asarray([features], dtype=float)
    current_fare = features[1]
    forecast_fare = max(0.0, float(fare_model.predict(row)[0]))
    change_percent = (forecast_fare - current_fare) / max(current_fare, 1.0) * 100
    surge_probability = float(surge_model.predict_proba(row)[0][1])
    if change_percent >= 3.0 or surge_probability >= 0.7:
        booking_window = "book_now"
        recommendation = "Book now to reduce exposure to an expected fare increase."
    elif change_percent <= -3.0:
        booking_window = "wait"
        recommendation = "Monitor fares; the model forecasts a lower fare."
    else:
        booking_window = "monitor"
        recommendation = "Monitor the fare and book when it fits your budget."
    confidence = regression_confidence(fare_model, features, forecast_fare) * max(
        surge_probability, 1.0 - surge_probability
    )
    return {
        "forecast_fare": round(forecast_fare, 2),
        "fare_change_percent": round(change_percent, 2),
        "demand_surge_probability": round(surge_probability, 4),
        "demand_surge": surge_probability >= 0.5,
        "optimal_booking_window": booking_window,
        "recommendation": recommendation,
        "confidence": round(confidence, 4),
        "explanation": explain_prediction(fare_model, features, FEATURE_NAMES),
    }
