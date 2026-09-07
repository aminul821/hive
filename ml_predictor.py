"""
ml_predictor.py
----------------
Loads the trained scikit-learn models and exposes a simple predict() function
for the Flask backend to call. Falls back gracefully with a clear error if the
model files haven't been trained yet (see train_model.py).
"""

import os
import joblib
import numpy as np
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RISK_MODEL_PATH = os.path.join(BASE_DIR, "models", "hive_risk_model.pkl")
YIELD_MODEL_PATH = os.path.join(BASE_DIR, "models", "hive_yield_model.pkl")

_risk_model = None
_yield_model = None


def _load():
    global _risk_model, _yield_model
    if _risk_model is not None:
        return
    if not (os.path.exists(RISK_MODEL_PATH) and os.path.exists(YIELD_MODEL_PATH)):
        raise RuntimeError(
            "ML models not found. Run 'python train_model.py' once to generate "
            "models/hive_risk_model.pkl and models/hive_yield_model.pkl"
        )
    _risk_model = joblib.load(RISK_MODEL_PATH)
    _yield_model = joblib.load(YIELD_MODEL_PATH)


def _reasons(temperature, humidity, weight, activity):
    """Human-readable factors, for explainability alongside the ML prediction."""
    reasons = []
    if temperature < 30 or temperature > 36:
        reasons.append("temperature outside preferred range (30-36°C)")
    if humidity < 45 or humidity > 75:
        reasons.append("humidity outside preferred range (45-75%)")
    if activity < 55:
        reasons.append("bee activity lower than expected")
    if weight < 35:
        reasons.append("hive weight lower than expected")
    return "; ".join(reasons) if reasons else "all monitored parameters are within a healthy range"


def predict(temperature: float, humidity: float, weight: float, activity: float) -> dict:
    """Returns a real ML-based prediction: risk category + confidence + yield estimate."""
    _load()
    import pandas as pd
    X = pd.DataFrame([[temperature, humidity, weight, activity]],
                      columns=["temperature", "humidity", "weight", "activity"])

    risk_pred = _risk_model.predict(X)[0]
    risk_proba = _risk_model.predict_proba(X)[0]
    confidence = float(max(risk_proba))

    yield_pred = float(_yield_model.predict(X)[0])

    return {
        "risk": risk_pred,
        "confidence": round(confidence * 100, 1),   # %
        "predicted_yield_kg": round(yield_pred, 1),
        "reason": _reasons(temperature, humidity, weight, activity),
        "model": "RandomForest (scikit-learn), trained on 4000 synthetic hive samples",
    }
