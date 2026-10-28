
import pytest

from app.services.ml_anomaly import MLAnomalyDetector


def test_detector_requires_training_before_scoring():
    detector = MLAnomalyDetector()

    with pytest.raises(RuntimeError, match="Train the detector"):
        detector.score([0, 1, 0, 1, 1, 2])


def test_detector_rejects_too_little_training_data():
    detector = MLAnomalyDetector()

    with pytest.raises(ValueError, match="At least 10"):
        detector.fit([[0, 1, 0, 1, 1, 2]] * 5)


def test_detector_can_train_and_score():
    detector = MLAnomalyDetector(random_state=42)

    # Synthetic data for a software smoke test only.
    training_data = [
        [
            (hour % 24) / 24,
            1.0,
            1.0,
            1.0,
            1.0,
            float(10 + hour % 3),
        ]
        for hour in range(20)
    ]

    detector.fit(training_data)
    result = detector.score([0.5, 0.5, 1, 1, 1, 11])

    assert result["model"] == "isolation_forest"
    assert result["prediction"] in (-1, 1)
    assert isinstance(result["is_anomalous"], bool)
    assert "decision_score" in result
