"""SHAP-based explanations for sklearn tree models."""

from typing import Any

import numpy as np
import shap


def explain_prediction(
    model: Any,
    features: list[float],
    feature_names: list[str],
    *,
    output_index: int = 0,
) -> list[dict[str, float | str]]:
    """Return signed SHAP contributions for one model output."""
    explainer = shap.TreeExplainer(model)
    raw_values = explainer.shap_values(
        np.asarray([features], dtype=float),
        check_additivity=False,
    )
    if isinstance(raw_values, list):
        values = np.asarray(raw_values[min(output_index, len(raw_values) - 1)])[0]
    else:
        values = np.asarray(raw_values)
        if values.ndim == 3:
            values = values[0, :, output_index]
        elif values.ndim == 2:
            values = values[0]

    explanation: list[dict[str, float | str]] = [
        {
            "feature": name,
            "value": float(value),
            "contribution": float(contribution),
            "effect": "increases" if contribution >= 0 else "decreases",
        }
        for name, value, contribution in zip(feature_names, features, values, strict=True)
    ]
    return sorted(explanation, key=lambda item: abs(float(item["contribution"])), reverse=True)


def regression_confidence(model: Any, features: list[float], prediction: float) -> float:
    """Estimate confidence from disagreement among trees in a random forest."""
    row = np.asarray([features], dtype=float)
    predictions = np.asarray([tree.predict(row)[0] for tree in model.estimators_], dtype=float)
    dispersion = float(predictions.std())
    return round(float(np.exp(-dispersion / max(abs(prediction), 1.0))), 4)
