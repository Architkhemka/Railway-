"""FastAPI application for dynamic fare predictions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from railway_ai_platform.ml.audit import record_audit_event
from railway_ai_platform.ml.metrics import PREDICTION_LATENCY, PREDICTIONS, metrics_payload
from railway_ai_platform.ml.tracking import load_latest_registered_model
from services.fare_prediction.model import (
    FARE_MODEL_NAME,
    SERVICE,
    SURGE_MODEL_NAME,
    fare_features,
    predict_fare,
)


class FarePredictionRequest(BaseModel):
    """Current fare, demand and departure horizon for an itinerary."""

    travel_class: str = Field(pattern="^(SL|3A|2A|1A|CC)$")
    base_fare: float = Field(gt=0, le=1_000_000)
    current_fare: float = Field(gt=0, le=1_000_000)
    demand_index: float = Field(ge=0, le=10)
    days_until_departure: int = Field(ge=0, le=365)


class FarePredictionResponse(BaseModel):
    """Fare forecast, surge risk, booking recommendation and explanation."""

    forecast_fare: float
    fare_change_percent: float
    demand_surge_probability: float
    demand_surge: bool
    optimal_booking_window: str
    recommendation: str
    confidence: float
    model_versions: dict[str, str]
    explanation: list[dict[str, Any]]


def create_app(
    fare_model: Any | None = None,
    surge_model: Any | None = None,
    versions: dict[str, str] | None = None,
) -> FastAPI:
    """Create the API with optional preloaded models for isolated tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if fare_model is not None and surge_model is not None:
            app.state.fare_model = fare_model
            app.state.surge_model = surge_model
            app.state.model_versions = versions or {"fare": "test", "surge": "test"}
        else:
            registered_fare, fare_version = load_latest_registered_model(FARE_MODEL_NAME)
            registered_surge, surge_version = load_latest_registered_model(SURGE_MODEL_NAME)
            app.state.fare_model = registered_fare
            app.state.surge_model = registered_surge
            app.state.model_versions = {"fare": fare_version, "surge": surge_version}
            record_audit_event(
                SERVICE,
                "models_loaded",
                {"fare_version": fare_version, "surge_version": surge_version},
            )
        yield

    app = FastAPI(title="Dynamic Fare Predictor", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        if not hasattr(request.app.state, "fare_model"):
            raise HTTPException(status_code=503, detail="models are not loaded")
        return {"status": "healthy", "model_versions": request.app.state.model_versions}

    @app.get("/metrics")
    def metrics() -> Response:
        body, content_type = metrics_payload()
        return Response(content=body, media_type=content_type)

    @app.post("/v1/fare/predict", response_model=FarePredictionResponse)
    def predict(body: FarePredictionRequest, request: Request) -> dict[str, Any]:
        if not hasattr(request.app.state, "fare_model"):
            raise HTTPException(status_code=503, detail="models are not loaded")
        features = fare_features(
            body.base_fare,
            body.current_fare,
            body.demand_index,
            body.days_until_departure,
            body.travel_class,
        )
        started = perf_counter()
        result = predict_fare(request.app.state.fare_model, request.app.state.surge_model, features)
        PREDICTIONS.labels(SERVICE).inc()
        PREDICTION_LATENCY.labels(SERVICE).observe(perf_counter() - started)
        result["model_versions"] = request.app.state.model_versions
        record_audit_event(
            SERVICE,
            "prediction_completed",
            {"model_versions": result["model_versions"]},
        )
        return result

    return app


app = create_app()
