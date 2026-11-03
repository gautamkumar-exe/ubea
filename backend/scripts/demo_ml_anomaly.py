"""Run an offline four-scenario UEBA feature and Isolation Forest demonstration."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from app.services.ml_anomaly import FEATURE_NAMES
from app.services.ml_experiments import fit_detector, load_synthetic_benchmark
from app.services.ml_features import features_for_event

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FIXTURE = SCRIPT_DIR / "reports" / "synthetic_events.csv"


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


def run_demo(
    fixture_path: Path = DEFAULT_FIXTURE,
    *,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 100,
) -> dict[str, object]:
    """Fit on train feature vectors only and score four controlled synthetic inputs."""
    benchmark = load_synthetic_benchmark(fixture_path)
    training_features = [
        row.features for row in benchmark.rows if row.split == "train"
    ]
    detector = fit_detector(
        training_features,
        contamination=contamination,
        random_state=random_state,
        n_estimators=n_estimators,
    )
    histories = _load_histories(fixture_path)
    user_history = histories["synthetic-user-001"]

    normal_time = datetime(2026, 10, 29, 9, tzinfo=timezone.utc)
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
            "Login at 02:00 UTC; the cyclic hour features differ from the generated daytime profile.",
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
            "Login from a valid but previously unseen test-network IP address.",
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
        "Twenty prior login_success events occurred within ten minutes for this controlled synthetic user.",
    ))

    reports = []
    for name, event, history, scenario_context in scenarios:
        feature_values = features_for_event(event, history)
        if any(value is None for value in feature_values):
            raise ValueError(f"Demo scenario {name} produced unavailable feature values")
        feature_vector = [float(value) for value in feature_values]
        scored = detector.score(feature_vector)
        score = float(scored["decision_score"])
        flagged = score < 0
        reports.append({
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
            "context": scenario_context,
            "interpretation": (
                "Score is below the fixed zero threshold. This is the detector decision, not a probability or proof of malicious activity."
                if flagged else
                "Score is at or above the fixed zero threshold. The event is not flagged by this model configuration; this does not establish that it is benign."
            ),
            "explainability_note": "Isolation Forest does not provide calibrated confidence or per-feature attribution here; the context describes input evidence, not causal feature importance.",
        })

    return {
        "demonstration_type": "offline_controlled_synthetic_ueba_demo",
        "feature_specification_version": "ueba-seven-v2",
        "fixture_sha256": benchmark.fixture_id,
        "training": {
            "training_rows": len(training_features),
            "partition": "chronological train split only",
            "scenario_labels_used_for_fit": False,
            "model_type": "IsolationForest",
            "contamination": contamination,
            "random_state": random_state,
            "n_estimators": n_estimators,
        },
        "features": list(FEATURE_NAMES),
        "threshold": "decision_function < 0",
        "results": reports,
        "warning": "Generated demonstration data only; not production performance, calibrated confidence, or evidence of a malicious event.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=100)
    args = parser.parse_args()
    result = run_demo(
        args.fixture,
        contamination=args.contamination,
        random_state=args.random_state,
        n_estimators=args.n_estimators,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
