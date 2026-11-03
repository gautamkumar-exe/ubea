"""Read-only, synthetic-only ML Analytics demonstration payload."""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.services.ml_anomaly import FEATURE_NAMES
from app.services.ml_dataset import FEATURE_SCHEMA_VERSION
from app.services.ml_experiments import (
    _binary_metrics,
    fit_detector,
    load_synthetic_benchmark,
)
from app.services.ml_features import features_for_event

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = BACKEND_ROOT / "scripts" / "reports" / "synthetic_events.csv"
FEATURE_SPECIFICATION_VERSION = FEATURE_SCHEMA_VERSION
DEMO_DISCLAIMER = (
    "All results use generated synthetic data and are for demonstration only. "
    "They are not production performance or evidence of malicious activity. "
    "Decision scores are not probabilities, and this demonstration does not "
    "create or update operational alerts."
)


def _load_histories(path: Path) -> dict[str, list[SimpleNamespace]]:
    histories: dict[str, list[SimpleNamespace]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            event = SimpleNamespace(
                user_id=row["user_id"],
                event_time=datetime.fromisoformat(row["event_time"].replace("Z", "+00:00")),
                event_type=row["event_type"],
                source_ip=row["source_ip"],
                source="synthetic-demo-fixture",
                external_id=None,
            )
            histories[event.user_id].append(event)
    for events in histories.values():
        events.sort(key=lambda event: event.event_time)
    return dict(histories)


def _build_scenarios(histories: dict[str, list[SimpleNamespace]]) -> list[tuple[str, SimpleNamespace, list[object], str]]:
    normal_time = datetime(2026, 10, 29, 9, tzinfo=timezone.utc)
    user_history = histories["synthetic-user-001"]
    scenarios: list[tuple[str, SimpleNamespace, list[object], str]] = [
        (
            "normal_login",
            SimpleNamespace(
                user_id="synthetic-user-001",
                event_time=normal_time,
                event_type="login_success",
                source_ip="192.0.2.10",
            ),
            user_history,
            "Expected daytime login using a previously observed event type and IP.",
        ),
        (
            "unusual_login_hour",
            SimpleNamespace(
                user_id="synthetic-user-001",
                event_time=normal_time.replace(hour=2),
                event_type="login_success",
                source_ip="192.0.2.10",
            ),
            user_history,
            "Login at 02:00 UTC; its cyclic hour features differ from the generated daytime profile.",
        ),
        (
            "unfamiliar_source_ip",
            SimpleNamespace(
                user_id="synthetic-user-001",
                event_time=normal_time,
                event_type="login_success",
                source_ip="203.0.113.250",
            ),
            user_history,
            "Login from a valid but previously unseen documentation-reserved IP.",
        ),
    ]

    burst_start = datetime(2026, 10, 30, 9, tzinfo=timezone.utc)
    burst_ips = ("192.0.2.10", "192.0.2.11", "192.0.2.12")
    burst_history = [
        SimpleNamespace(
            user_id="synthetic-burst-user",
            event_time=burst_start + timedelta(seconds=30 * index),
            event_type="login_success",
            source_ip=burst_ips[index % len(burst_ips)],
        )
        for index in range(20)
    ]
    scenarios.append((
        "high_authentication_frequency",
        SimpleNamespace(
            user_id="synthetic-burst-user",
            event_time=burst_start + timedelta(minutes=20),
            event_type="login_success",
            source_ip="192.0.2.10",
        ),
        burst_history,
        "Twenty prior login_success events occurred within ten minutes for this synthetic user.",
    ))
    return scenarios


def run_ml_analytics_demo(
    fixture_path: Path = DEFAULT_FIXTURE,
    *,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 100,
) -> dict[str, Any]:
    """Compute demo scores and synthetic held-out metrics entirely in memory."""
    benchmark = load_synthetic_benchmark(Path(fixture_path))
    training_rows = [row for row in benchmark.rows if row.split == "train"]
    if len(training_rows) < 10:
        raise ValueError("Synthetic benchmark has too few chronological training rows")
    detector = fit_detector(
        [row.features for row in training_rows],
        contamination=contamination,
        random_state=random_state,
        n_estimators=n_estimators,
    )

    demo_rows = []
    for name, event, history, context in _build_scenarios(_load_histories(Path(fixture_path))):
        values = features_for_event(event, history)
        if any(value is None for value in values):
            raise ValueError(f"Demo scenario {name} produced unavailable feature values")
        feature_vector = [float(value) for value in values]
        result = detector.score(feature_vector)
        score = float(result["decision_score"])
        flagged = score < 0
        demo_rows.append({
            "scenario": name,
            "input_event": {
                "user_id": event.user_id,
                "event_time_utc": event.event_time.astimezone(timezone.utc).isoformat(),
                "event_type": event.event_type,
                "source_ip": event.source_ip,
            },
            "features": dict(zip(FEATURE_NAMES, feature_vector)),
            "decision_score": score,
            "prediction": "ANOMALY" if flagged else "NOT FLAGGED",
            "threshold_rule": "decision_function < 0",
            "context": context,
            "interpretation": (
                "Score is below the fixed zero threshold. This is a detector decision, not a probability or proof of malicious activity."
                if flagged
                else "Score is at or above the fixed zero threshold. This does not establish that the event is benign."
            ),
        })

    test_rows = [row for row in benchmark.rows if row.split == "test"]
    test_scores = [detector.score(row.features) for row in test_rows]
    scenarios = [row.scenario for row in test_rows]
    predictions = [bool(score["is_anomalous"]) for score in test_scores]
    metrics = _binary_metrics(scenarios, predictions)
    normal_count = metrics["true_negative"] + metrics["false_positive"]
    false_positive_rate = metrics["false_positive"] / normal_count if normal_count else None

    scenario_results: dict[str, dict[str, int | float | None]] = {}
    for scenario_name in sorted(set(scenarios)):
        pairs = [
            (row, score)
            for row, score in zip(test_rows, test_scores)
            if row.scenario == scenario_name
        ]
        predicted_anomalies = sum(bool(score["is_anomalous"]) for _, score in pairs)
        support = len(pairs)
        scenario_results[scenario_name] = {
            "support": support,
            "predicted_anomalies": predicted_anomalies,
            "predicted_anomaly_rate": predicted_anomalies / support if support else None,
        }

    return {
        "demonstration_type": "offline_controlled_synthetic_ueba_demo",
        "feature_specification_version": FEATURE_SPECIFICATION_VERSION,
        "fixture_sha256": benchmark.fixture_id,
        "model": {
            "name": "Isolation Forest",
            "implementation": "scikit-learn IsolationForest",
            "feature_specification_version": FEATURE_SPECIFICATION_VERSION,
            "features": list(FEATURE_NAMES),
            "configuration": {
                "contamination": contamination,
                "random_state": random_state,
                "n_estimators": n_estimators,
            },
            "training": {
                "records": len(training_rows),
                "partition": "chronological train split only",
                "scenario_labels_used_for_fit": False,
            },
            "decision_rule": {
                "score_name": "decision_function",
                "operator": "<",
                "threshold": 0.0,
                "note": "Fixed zero decision threshold; not a probability threshold.",
            },
        },
        "training": {
            "training_rows": len(training_rows),
            "partition": "chronological train split only",
            "scenario_labels_used_for_fit": False,
            "model_type": "IsolationForest",
            "contamination": contamination,
            "random_state": random_state,
            "n_estimators": n_estimators,
        },
        "features": list(FEATURE_NAMES),
        "threshold": "decision_function < 0",
        "results": demo_rows,
        "benchmark_evaluation": {
            "dataset_kind": "deterministic_synthetic_fixture",
            "evaluation_status": "synthetic_ground_truth_only",
            "label_source": "Synthetic generator scenario labels; evaluation only.",
            "fixture_sha256": benchmark.fixture_id,
            "feature_specification_version": FEATURE_SPECIFICATION_VERSION,
            "evaluation_split": "chronological test split",
            "test_records": len(test_rows),
            "threshold": "decision_function < 0",
            "metrics": {
                "precision": metrics["precision"],
                "recall": metrics["recall"],
                "f1": metrics["f1"],
                "false_positive_rate": false_positive_rate,
                "confusion_matrix": metrics["confusion_matrix"],
            },
            "scenario_results": scenario_results,
            "warning": "Synthetic scenario metrics are not production performance or confirmation of malicious activity.",
        },
        "warning": DEMO_DISCLAIMER,
    }
