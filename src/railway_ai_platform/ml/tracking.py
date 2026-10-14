"""MLflow tracking and model registry helpers shared by prediction services."""

import os
from typing import Any

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient


def tracking_uri() -> str:
    """Return the configured MLflow tracking server URI."""
    return os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")


def log_and_register_model(
    model: Any,
    *,
    model_name: str,
    service_name: str,
    dataset_name: str,
    row_count: int,
    metrics: dict[str, float],
) -> str:
    """Log a fitted sklearn model and metrics, then register a new model version."""
    mlflow.set_tracking_uri(tracking_uri())
    mlflow.set_experiment(f"railway-{service_name}")
    with mlflow.start_run(run_name=f"{service_name}-training") as run:
        mlflow.log_params(
            {
                "dataset": dataset_name,
                "row_count": row_count,
                "random_state": 42,
                "model_type": type(model).__name__,
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=model_name,
        )
        return str(run.info.run_id)


def load_latest_registered_model(model_name: str) -> tuple[Any, str]:
    """Load the highest-version registered model and return its version."""
    mlflow.set_tracking_uri(tracking_uri())
    client = MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        raise RuntimeError(f"no registered MLflow model found for {model_name}")
    latest = max(versions, key=lambda version: int(version.version))
    model = mlflow.sklearn.load_model(f"models:/{model_name}/{latest.version}")
    return model, str(latest.version)
