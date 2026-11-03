from fastapi.testclient import TestClient

from app.main import app


def test_ml_analytics_demo_api_returns_synthetic_scenarios_and_benchmark() -> None:
    with TestClient(app) as client:
        response = client.get("/ml-analytics/demo")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["feature_specification_version"] == "ueba-seven-v2"
    assert result["model"]["name"] == "Isolation Forest"
    assert result["model"]["training"]["scenario_labels_used_for_fit"] is False
    assert result["model"]["decision_rule"]["threshold"] == 0.0
    assert len(result["results"]) == 4

    scenarios = {row["scenario"]: row for row in result["results"]}
    assert scenarios["normal_login"]["prediction"] == "NOT FLAGGED"
    assert scenarios["unusual_login_hour"]["prediction"] == "ANOMALY"
    assert scenarios["unfamiliar_source_ip"]["prediction"] == "ANOMALY"
    assert scenarios["high_authentication_frequency"]["prediction"] == "ANOMALY"
    for row in scenarios.values():
        assert len(row["features"]) == 7
        assert isinstance(row["decision_score"], float)
        assert "probability" not in row
        assert "confidence" not in row

    benchmark = result["benchmark_evaluation"]
    assert benchmark["evaluation_status"] == "synthetic_ground_truth_only"
    assert benchmark["test_records"] == 218
    assert benchmark["metrics"]["precision"] == 22 / 39
    assert benchmark["metrics"]["recall"] == 0.88
    assert benchmark["metrics"]["f1"] == 0.6875
    assert benchmark["metrics"]["false_positive_rate"] == 17 / 193
    assert benchmark["metrics"]["confusion_matrix"]["values"] == [[176, 17], [3, 22]]
    assert "not production performance" in benchmark["warning"]
