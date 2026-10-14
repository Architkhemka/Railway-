"""Prometheus metrics shared by the model-serving APIs."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

PREDICTIONS = Counter(
    "railway_predictions_total",
    "Number of completed prediction requests",
    ("service",),
)
PREDICTION_LATENCY = Histogram(
    "railway_prediction_duration_seconds",
    "Prediction request duration in seconds",
    ("service",),
)


def metrics_payload() -> tuple[bytes, str]:
    """Return metrics in Prometheus exposition format."""
    return generate_latest(), CONTENT_TYPE_LATEST
