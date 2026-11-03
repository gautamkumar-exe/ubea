from pathlib import Path

from scripts.demo_ml_anomaly import DEFAULT_FIXTURE, run_demo


def test_offline_demo_uses_v2_and_shows_four_controlled_scenarios() -> None:
    result = run_demo(Path(DEFAULT_FIXTURE))

    assert result["demonstration_type"] == "offline_controlled_synthetic_ueba_demo"
    assert result["feature_specification_version"] == "ueba-seven-v2"
    assert result["training"]["training_rows"] == 1077
    assert result["training"]["partition"] == "chronological train split only"
    assert result["training"]["scenario_labels_used_for_fit"] is False
    assert result["threshold"] == "decision_function < 0"

    rows = {row["scenario"]: row for row in result["results"]}
    assert set(rows) == {
        "normal_login",
        "unusual_login_hour",
        "unfamiliar_source_ip",
        "high_authentication_frequency",
    }
    assert rows["normal_login"]["prediction"] == "NOT FLAGGED"
    assert rows["unusual_login_hour"]["prediction"] == "ANOMALY"
    assert rows["unfamiliar_source_ip"]["prediction"] == "ANOMALY"
    assert rows["high_authentication_frequency"]["prediction"] == "ANOMALY"
    assert rows["high_authentication_frequency"]["features"]["user_event_frequency"] > 3

    for row in rows.values():
        assert set(row["features"]) == set(result["features"])
        assert "decision_score" in row
        assert "probability" not in row
        assert "confidence" not in row


def test_offline_demo_is_deterministic() -> None:
    first = run_demo()
    second = run_demo()

    assert first == second
