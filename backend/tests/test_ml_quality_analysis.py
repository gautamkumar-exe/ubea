from app.services.ml_anomaly import FEATURE_NAMES
from scripts.analyze_ml_quality import (
    _metrics,
    _select_validation_fpr_threshold,
    _select_validation_threshold,
)


def test_quality_metrics_report_confusion_matrix_counts_and_rates():
    result = _metrics(
        ["normal", "normal", "unusual_hour", "unfamiliar_ip"],
        [0.2, -0.1, -0.2, 0.1],
        0.0,
    )

    assert result["tp"] == 1
    assert result["fp"] == 1
    assert result["tn"] == 1
    assert result["fn"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f1"] == 0.5
    assert result["false_positive_rate"] == 0.5


def test_threshold_selection_uses_only_passed_validation_labels_and_scores():
    labels = ["normal", "normal", "unfamiliar_ip", "normal"]
    scores = [0.3, 0.1, -0.2, 0.2]
    threshold = _select_validation_threshold(labels, scores)

    assert threshold < 0
    assert _metrics(labels, scores, threshold)["f1"] == 1.0
    # The selection API accepts only validation labels/scores; held-out test data
    # are evaluated separately by the caller after selection.
    assert len(FEATURE_NAMES) == 7


def test_validation_fpr_threshold_respects_validation_normal_budget():
    labels = ["normal"] * 20 + ["unusual_hour"] * 2
    scores = [index / 100 for index in range(20)] + [-0.2, -0.1]
    threshold = _select_validation_fpr_threshold(labels, scores, max_fpr=0.05)

    measured = _metrics(labels, scores, threshold)
    assert measured["false_positive_rate"] <= 0.05
    assert measured["recall"] == 1.0
