
import pytest

from app.services.ml_anomaly import FEATURE_NAMES, MLAnomalyDetector


def test_detector_requires_training_before_scoring():
    detector = MLAnomalyDetector()

    with pytest.raises(RuntimeError, match="Train the detector"):
        detector.score([0.0] * len(FEATURE_NAMES))


def test_detector_rejects_too_little_training_data():
    detector = MLAnomalyDetector()

    with pytest.raises(ValueError, match="At least 10"):
        detector.fit([[0.0] * len(FEATURE_NAMES)] * 5)


def test_detector_can_train_and_score():
    detector = MLAnomalyDetector(random_state=42)

    # Synthetic data for a software smoke test only.
    training_data = [
        [
            float(hour % 24) / 24,
            1.0,
            1.0,
            1.0,
            1.0,
            float(10 + hour % 3),
            float(hour % 4),
        ]
        for hour in range(20)
    ]

    detector.fit(training_data)

    result = detector.score(training_data[0])

    assert result["model"] == "isolation_forest"
    assert isinstance(result["is_anomalous"], bool)
    assert isinstance(result["decision_score"], float)
    assert len(result["features"]) == len(FEATURE_NAMES)
    assert "source_ip_frequency" in result["features"]
