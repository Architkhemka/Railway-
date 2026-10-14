"""Training and inference logic for delay and disruption predictions."""

from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

from railway_ai_platform.data.generators import GenerationOptions
from railway_ai_platform.data.loader import SyntheticDataLoader
from railway_ai_platform.ml.audit import record_audit_event
from railway_ai_platform.ml.explainability import explain_prediction, regression_confidence
from railway_ai_platform.ml.tracking import log_and_register_model

SERVICE = "delay_prediction"
MODEL_NAME = "railway-delay-disruption"
FEATURE_NAMES = ["historical_delay_minutes", "station_code", "observation_hour"]
STATIONS = (
    "PUNE",
    "DELHI",
    "MUMBAI",
    "BENGALURU",
    "CHENNAI",
    "HYDERABAD",
    "KOLKATA",
    "AHMEDABAD",
    "JAIPUR",
    "LUCKNOW",
)
_STATION_CODE = {station: float(index) for index, station in enumerate(STATIONS)}


def delay_features(
    historical_delay_minutes: int,
    station_code: str,
    observation_hour: int,
) -> list[float]:
    """Encode the latest delay observation and station for model inference."""
    return [
        float(historical_delay_minutes),
        _STATION_CODE.get(station_code, float(len(STATIONS))),
        float(observation_hour),
    ]


def train_model(count: int = 1_200) -> str:
    """Train from reproducible synthetic delay observations and register the model."""
    if count < 100:
        raise ValueError("delay prediction training requires at least 100 synthetic rows")
    rows = SyntheticDataLoader(GenerationOptions(count=count, seed=42)).load("delays")
    features: list[list[float]] = []
    targets: list[list[float]] = []
    for row in rows:
        delay = float(row["delay_minutes"] or 0)
        congestion = float(row["congestion_level"] or 0)
        station = str(row["station_code"])
        hour = int(str(row["observed_at"])[11:13])
        features.append(delay_features(int(delay), station, hour))
        station_factor = _STATION_CODE[station] % 4
        arrival_delay = max(0.0, delay * (0.65 + congestion * 0.5) + station_factor)
        departure_delay = max(0.0, delay * (0.35 + congestion * 0.35) + station_factor / 2)
        forecast_congestion = float(np.clip(0.15 + delay / 120 + congestion * 0.2, 0.0, 1.0))
        targets.append([arrival_delay, departure_delay, forecast_congestion])

    matrix = np.asarray(features, dtype=float)
    target = np.asarray(targets, dtype=float)
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(matrix, target)
    errors = mean_absolute_error(target, model.predict(matrix), multioutput="raw_values")
    run_id = log_and_register_model(
        model,
        model_name=MODEL_NAME,
        service_name=SERVICE,
        dataset_name="synthetic train delays",
        row_count=len(target),
        metrics={
            "arrival_delay_training_mae": float(errors[0]),
            "departure_delay_training_mae": float(errors[1]),
            "congestion_training_mae": float(errors[2]),
        },
    )
    record_audit_event(
        SERVICE,
        "model_registered",
        {"model": MODEL_NAME, "run_id": run_id, "training_rows": len(target)},
    )
    return run_id


def predict_delay(model: Any, features: list[float]) -> dict[str, Any]:
    """Predict delays and congestion, with risk alerts and SHAP explanations."""
    row = np.asarray([features], dtype=float)
    predicted = model.predict(row)[0]
    arrival = max(0.0, float(predicted[0]))
    departure = max(0.0, float(predicted[1]))
    congestion = float(np.clip(predicted[2], 0.0, 1.0))
    confidence = regression_confidence(model, features, arrival)
    alert_reasons: list[str] = []
    if arrival >= 30:
        alert_reasons.append("high_arrival_delay")
    if congestion >= 0.75:
        alert_reasons.append("high_station_congestion")
    alternatives = (
        [
            "Consider a later departure on the same route",
            "Check nearby stations for alternate services",
        ]
        if alert_reasons
        else []
    )
    return {
        "arrival_delay_minutes": round(arrival, 1),
        "departure_delay_minutes": round(departure, 1),
        "station_congestion": round(congestion, 4),
        "proactive_alerts": alert_reasons,
        "alternative_options": alternatives,
        "confidence": confidence,
        "explanation": explain_prediction(model, features, FEATURE_NAMES, output_index=0),
    }
