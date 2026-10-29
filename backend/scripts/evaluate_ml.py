from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.services.ml_anomaly import MLAnomalyDetector
from app.services.ml_features import features_for_event

BASE_DIR = Path(__file__).resolve().parent
INPUT_CSV = BASE_DIR / "reports" / "synthetic_events.csv"
REPORT_DIR = BASE_DIR / "reports"
TRAIN_RATIO = 0.80
MIN_TRAIN_EVENTS = 10
CONTAMINATION = 0.05


def load_events():
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"{INPUT_CSV} not found. Run generate_synthetic_events.py first."
        )

    users = defaultdict(list)

    with INPUT_CSV.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            event = SimpleNamespace(
                user_id=row["user_id"],
                event_time=datetime.fromisoformat(row["event_time"]),
                event_type=row["event_type"],
                source_ip=row["source_ip"],
                scenario=row["scenario"],
            )
            users[event.user_id].append(event)

    for events in users.values():
        events.sort(key=lambda e: e.event_time)

    return users


def evaluate_user(user_id, events):
    if len(events) < MIN_TRAIN_EVENTS + 1:
        print(f"Skipping {user_id}: insufficient events ({len(events)}).")
        return []

    split = int(len(events) * TRAIN_RATIO)
    split = max(MIN_TRAIN_EVENTS, min(split, len(events) - 1))

    training_events = events[:split]
    test_events = events[split:]

    history = []
    training_features = []

    # Train on normal events only, using past events for each feature row.
    for event in training_events:
        features = features_for_event(event, history)

        if event.scenario == "normal":
            training_features.append(features)

        history.append(event)

    if len(training_features) < MIN_TRAIN_EVENTS:
        print(
            f"Skipping {user_id}: only {len(training_features)} "
            "normal training rows."
        )
        return []

    detector = MLAnomalyDetector(
        contamination=CONTAMINATION,
        random_state=42,
    )
    detector.fit(training_features)

    results = []

    # Evaluate chronologically. Each event sees only earlier events.
    for event in test_events:
        features = features_for_event(event, history)
        prediction = detector.score(features)

        actual = event.scenario != "normal"
        predicted = prediction["is_anomalous"]

        results.append({
            "user_id": user_id,
            "event_time": event.event_time.isoformat(),
            "event_type": event.event_type,
            "source_ip": event.source_ip,
            "scenario": event.scenario,
            "actual_anomaly": actual,
            "predicted_anomaly": predicted,
            "decision_score": prediction["decision_score"],
            "features": json.dumps(
                prediction["features"], sort_keys=True
            ),
            "training_rows": len(training_features),
        })

        history.append(event)

    print(
        f"{user_id}: train={len(training_features)} normal rows, "
        f"test={len(results)} events, "
        f"flagged={sum(r['predicted_anomaly'] for r in results)}"
    )
    return results


def safe_ratio(numerator, denominator):
    return numerator / denominator if denominator else 0.0


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    users = load_events()

    results = []
    for user_id, events in sorted(users.items()):
        results.extend(evaluate_user(user_id, events))

    if not results:
        print("No evaluation results. Check the dataset and event counts.")
        return

    tp = sum(r["actual_anomaly"] and r["predicted_anomaly"] for r in results)
    fp = sum(not r["actual_anomaly"] and r["predicted_anomaly"] for r in results)
    fn = sum(r["actual_anomaly"] and not r["predicted_anomaly"] for r in results)
    tn = sum(not r["actual_anomaly"] and not r["predicted_anomaly"] for r in results)

    precision = safe_ratio(tp, tp + fp)
    recall = safe_ratio(tp, tp + fn)
    f1 = safe_ratio(2 * precision * recall, precision + recall)

    summary = {
        "model": "IsolationForest",
        "dataset": "synthetic",
        "training_ratio": TRAIN_RATIO,
        "contamination": CONTAMINATION,
        "test_events": len(results),
        "actual_anomalies": tp + fn,
        "predicted_anomalies": tp + fp,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "accuracy": round(safe_ratio(tp + tn, len(results)), 4),
        "warning": (
            "Synthetic-data metrics only; they do not establish "
            "real-world security detection performance."
        ),
    }

    csv_path = REPORT_DIR / "ml_evaluation.csv"
    json_path = REPORT_DIR / "ml_evaluation_summary.json"

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== SYNTHETIC ML EVALUATION ===")
    print(json.dumps(summary, indent=2))
    print(f"\nEvent report: {csv_path}")
    print(f"Summary report: {json_path}")


if __name__ == "__main__":
    main()
