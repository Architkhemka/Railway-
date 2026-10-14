"""FastAPI application for ticket confirmation predictions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from railway_ai_platform.ml.audit import record_audit_event
from railway_ai_platform.ml.metrics import PREDICTION_LATENCY, PREDICTIONS, metrics_payload
from railway_ai_platform.ml.tracking import load_latest_registered_model
from services.ticket_confirmation.model import (
    MODEL_NAME,
    SERVICE,
    predict_ticket,
    ticket_features,
)


class TicketPredictionRequest(BaseModel):
    """Inputs needed to estimate a WL/RAC ticket outcome."""

    ticket_status: str = Field(pattern="^(WL|RAC)$")
    waitlist_position: int = Field(ge=1, le=500)
    days_until_departure: int = Field(ge=0, le=365)
    travel_class: str = Field(pattern="^(SL|3A|2A|1A|CC)$")


class TicketPredictionResponse(BaseModel):
    """Ticket confirmation estimate and explainability response."""

    confirmation_probability: float
    final_berth_status: str
    confidence: float
    model_version: str
    explanation: list[dict[str, Any]]


def create_app(model: Any | None = None, version: str = "unavailable") -> FastAPI:
    """Create the service API; model injection keeps endpoint tests isolated."""

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

    app = FastAPI(title="Ticket Confirmation Predictor", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    def health(request: Request) -> dict[str, str]:
        if not hasattr(request.app.state, "model"):
            raise HTTPException(status_code=503, detail="model is not loaded")
        return {"status": "healthy", "model_version": request.app.state.model_version}

    @app.get("/metrics")
    def metrics() -> Response:
        body, content_type = metrics_payload()
        return Response(content=body, media_type=content_type)

    @app.post("/v1/ticket/predict", response_model=TicketPredictionResponse)
    def predict(body: TicketPredictionRequest, request: Request) -> dict[str, Any]:
        if not hasattr(request.app.state, "model"):
            raise HTTPException(status_code=503, detail="model is not loaded")
        features = ticket_features(
            body.ticket_status,
            body.waitlist_position,
            body.days_until_departure,
            body.travel_class,
        )
        started = perf_counter()
        result = predict_ticket(request.app.state.model, features)
        PREDICTIONS.labels(SERVICE).inc()
        PREDICTION_LATENCY.labels(SERVICE).observe(perf_counter() - started)
        result["model_version"] = request.app.state.model_version
        record_audit_event(
            SERVICE,
            "prediction_completed",
            {"ticket_status": body.ticket_status, "model_version": result["model_version"]},
        )
        return result

    return app


app = create_app()
