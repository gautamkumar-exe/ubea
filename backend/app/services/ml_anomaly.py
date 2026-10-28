
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


FEATURE_NAMES = (
    "hour_sin",
    "hour_cos",
    "is_login",
    "is_known_ip",
    "is_known_event_type",
    "user_event_frequency",
)


@dataclass
class MLAnomalyDetector:
    """Experimental Isolation Forest detector for UEBA events."""

    contamination: float = 0.05
    random_state: int = 42

    def __post_init__(self) -> None:
        if not 0 < self.contamination <= 0.5:
            raise ValueError("contamination must be in (0, 0.5]")

        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=100,
            contamination=self.contamination,
            random_state=self.random_state,
        )
        self.is_fitted = False

    def fit(self, training_data: Sequence[Sequence[float]]) -> None:
        """Train on historical, representative normal-behavior features."""
        X = np.asarray(training_data, dtype=float)

        if X.ndim != 2 or X.shape[1] != len(FEATURE_NAMES):
            raise ValueError(
                f"Expected a 2D array with {len(FEATURE_NAMES)} features"
            )

        if len(X) < 10:
            raise ValueError(
                "At least 10 historical events are required for this "
                "experimental model."
            )

        if not np.isfinite(X).all():
            raise ValueError("Training data must contain finite numbers")

        self.scaler.fit(X)
        self.model.fit(self.scaler.transform(X))
        self.is_fitted = True

    def score(self, features: Sequence[float]) -> dict:
        """Return an anomaly prediction and a relative anomaly score."""
        if not self.is_fitted:
            raise RuntimeError("Train the detector before scoring events")

        X = np.asarray(features, dtype=float)

        if X.shape != (len(FEATURE_NAMES),):
            raise ValueError(
                f"Expected exactly {len(FEATURE_NAMES)} feature values"
            )

        if not np.isfinite(X).all():
            raise ValueError("Features must contain finite numbers")

        X_scaled = self.scaler.transform(X.reshape(1, -1))
        prediction = int(self.model.predict(X_scaled)[0])
        decision_score = float(self.model.decision_function(X_scaled)[0])

        return {
            "model": "isolation_forest",
            "is_anomalous": prediction == -1,
            "prediction": prediction,
            "decision_score": decision_score,
            "features": dict(zip(FEATURE_NAMES, X.tolist())),
            "note": (
                "Experimental unsupervised model output. This score is "
                "not a probability or proof of malicious activity."
            ),
        }
