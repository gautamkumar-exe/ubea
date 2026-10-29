import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ml_anomaly import MLAnomalyDetector
from app.services.ml_features import features_for_event

BASE = Path(__file__).resolve().parent
INPUT = BASE / "reports" / "synthetic_events.csv"
SETTINGS = [0.01, 0.02, 0.03, 0.05]
TRAIN_RATIO = 0.80
MIN_TRAIN = 10


def load_data():
    users = defaultdict(list)
    with INPUT.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
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


def evaluate(users, contamination):
    results = []

    for user_id, events in sorted(users.items()):
        if len(events) <= MIN_TRAIN:
            continue

        split = max(MIN_TRAIN, min(int(len(events) * TRAIN_RATIO), len(events) - 1))
        training, testing = events[:split], events[split:]

        history = []
        X_train = []

        for event in training:
            features = features_for_event(event, history)
            if event.scenario == "normal":
                X_train.append(features)
            history.append(event)

        if len(X_train) < MIN_TRAIN:
            continue

        detector = MLAnomalyDetector(
            contamination=contamination,
            random_state=42,
        )
        detector.fit(X_train)

        for event in testing:
            prediction = detector.score(features_for_event(event, history))
            results.append({
                "user_id": user_id,
                "scenario": event.scenario,
                "actual": event.scenario != "normal",
                "predicted": prediction["is_anomalous"],
                "score": prediction["decision_score"],
            })
            history.append(event)

    tp = sum(r["actual"] and r["predicted"] for r in results)
    fp = sum(not r["actual"] and r["predicted"] for r in results)
    fn = sum(r["actual"] and not r["predicted"] for r in results)
    tn = sum(not r["actual"] and not r["predicted"] for r in results)

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

    return {
        "contamination": contamination,
        "test_events": len(results),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
    }


def main():
    if not INPUT.exists():
        raise FileNotFoundError(
            f"{INPUT} not found. Run generate_synthetic_events.py first."
        )

    users = load_data()
    results = [evaluate(users, value) for value in SETTINGS]

    print(json.dumps(results, indent=2))
    output = BASE / "reports" / "contamination_comparison.json"
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved comparison to: {output}")


if __name__ == "__main__":
    main()
