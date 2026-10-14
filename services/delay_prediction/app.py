"""FastAPI application for train delay and disruption predictions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from railway_ai_platform.ml.audit import record_audit_event
from railway_ai_platform.ml.metrics import PREDICTION_LATENCY, PREDICTIONS, metrics_payload
from railway_ai_platform.ml.tracking import load_latest_registered_model
from services.delay_prediction.model import (
    MODEL_NAME,
    SERVICE,
    delay_features,
    predict_delay,
)


class DelayPredictionRequest(BaseModel):
    """Latest observable train and station context for delay estimation."""

    train_number: str = Field(min_length=1, max_length=20)
    station_code: str = Field(min_length=2, max_length=12)
    historical_delay_minutes: int = Field(ge=0, le=1_440)
    observation_hour: int = Field(ge=0, le=23)


class DelayPredictionResponse(BaseModel):
    """Predicted train delays, station congestion, alerts, and rationale."""

    arrival_delay_minutes: float
    departure_delay_minutes: float
    station_congestion: float
    proactive_alerts: list[str]
    alternative_options: list[str]
    confidence: float
    model_version: str
    explanation: list[dict[str, Any]]


def create_app(model: Any | None = None, version: str = "unavailable") -> FastAPI:
    """Create the API with an optional preloaded model for isolated tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if model is not None:
            app.state.model = model
            app.state.model_version = version
        else:
            registered_model, registered_version = load_latest_registered_model(MODEL_NAME)
            app.state.model = registered_model
            app.state.model_version = registered_version
            record_audit_event(
                SERVICE,
                "model_loaded",
                {"model": MODEL_NAME, "model_version": registered_version},
            )
        yield

    app = FastAPI(title="Train Delay and Disruption Predictor", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    def health(request: Request) -> dict[str, str]:
        if not hasattr(request.app.state, "model"):
            raise HTTPException(status_code=503, detail="model is not loaded")
        return {"status": "healthy", "model_version": request.app.state.model_version}

    @app.get("/metrics")
    def metrics() -> Response:
        body, content_type = metrics_payload()
        return Response(content=body, media_type=content_type)

    @app.post("/v1/delay/predict", response_model=DelayPredictionResponse)
    def predict(body: DelayPredictionRequest, request: Request) -> dict[str, Any]:
        if not hasattr(request.app.state, "model"):
            raise HTTPException(status_code=503, detail="model is not loaded")
        features = delay_features(
            body.historical_delay_minutes,
            body.station_code,
            body.observation_hour,
        )
        started = perf_counter()
        result = predict_delay(request.app.state.model, features)
        PREDICTIONS.labels(SERVICE).inc()
        PREDICTION_LATENCY.labels(SERVICE).observe(perf_counter() - started)
        result["model_version"] = request.app.state.model_version
        record_audit_event(
            SERVICE,
            "prediction_completed",
            {"train_number": body.train_number, "model_version": result["model_version"]},
        )
        return result

    return app


app = create_app()
