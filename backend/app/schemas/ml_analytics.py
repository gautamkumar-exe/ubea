from typing import Any, Literal

from pydantic import BaseModel


class MLModelConfiguration(BaseModel):
    contamination: float
    random_state: int
    n_estimators: int


class MLTrainingSummary(BaseModel):
    records: int
    partition: str
    scenario_labels_used_for_fit: Literal[False]


class MLDecisionRule(BaseModel):
    score_name: str
    operator: str
    threshold: float
    note: str


class MLModelInfo(BaseModel):
    name: str
    implementation: str
    feature_specification_version: str
    features: list[str]
    configuration: MLModelConfiguration
    training: MLTrainingSummary
    decision_rule: MLDecisionRule


class MLDemoInputEvent(BaseModel):
    user_id: str
    event_time_utc: str
    event_type: str
    source_ip: str


class MLDemoScenario(BaseModel):
    scenario: str
    input_event: MLDemoInputEvent
    features: dict[str, float]
    decision_score: float
    prediction: Literal["ANOMALY", "NOT FLAGGED"]
    threshold_rule: str
    context: str
    interpretation: str


class MLConfusionMatrix(BaseModel):
    labels: list[str]
    values: list[list[int]]


class MLBenchmarkMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    false_positive_rate: float | None
    confusion_matrix: MLConfusionMatrix


class MLScenarioEvaluation(BaseModel):
    support: int
    predicted_anomalies: int
    predicted_anomaly_rate: float | None


class MLSyntheticBenchmarkEvaluation(BaseModel):
    dataset_kind: str
    evaluation_status: str
    label_source: str
    fixture_sha256: str
    feature_specification_version: str
    evaluation_split: str
    test_records: int
    threshold: str
    metrics: MLBenchmarkMetrics
    scenario_results: dict[str, MLScenarioEvaluation]
    warning: str


class MLAnalyticsDemoResponse(BaseModel):
    demonstration_type: str
    feature_specification_version: str
    fixture_sha256: str
    model: MLModelInfo
    training: dict[str, Any]
    features: list[str]
    threshold: str
    results: list[MLDemoScenario]
    benchmark_evaluation: MLSyntheticBenchmarkEvaluation
    warning: str
