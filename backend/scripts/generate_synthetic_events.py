from __future__ import annotations

import csv
import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "reports" / "synthetic_events.csv"

SEED = 42
USER_COUNT = 5
DAYS = 60

NORMAL_IPS = ["192.0.2.10", "192.0.2.11", "192.0.2.12"]
UNUSUAL_IPS = ["203.0.113.77", "203.0.113.88"]
EVENT_TYPES = ["login_success", "file_access", "app_access"]

INJECTED_ANOMALIES = {
    50: "unfamiliar_ip",
    52: "unusual_hour",
    54: "unfamiliar_ip",
    56: "unusual_hour",
    58: "unfamiliar_ip",
    59: "unusual_hour",
}


def main() -> None:
    rng = random.Random(SEED)

    end = datetime(2026, 10, 29, tzinfo=timezone.utc)
    start = end - timedelta(days=DAYS)
    rows = []

    for user_number in range(1, USER_COUNT + 1):
        user_id = f"synthetic-user-{user_number:03d}"
        usual_start = 8 + (user_number % 3)
        usual_end = usual_start + 9

        for day in range(DAYS):
            date = start + timedelta(days=day)

            for _ in range(rng.randint(4, 6)):
                event_time = date.replace(
                    hour=rng.randint(usual_start, usual_end),
                    minute=rng.choice([0, 15, 30, 45]),
                )
                rows.append({
                    "user_id": user_id,
                    "event_time": event_time.isoformat(),
                    "event_type": rng.choices(
                        EVENT_TYPES, weights=[0.65, 0.20, 0.15]
                    )[0],
                    "source_ip": rng.choice(NORMAL_IPS),
                    "scenario": "normal",
                })

            scenario = INJECTED_ANOMALIES.get(day)
            if scenario is None:
                continue

            if scenario == "unfamiliar_ip":
                hour = rng.randint(usual_start, usual_end)
                source_ip = f"203.0.113.{100 + day}"
            else:
                hour = rng.choice([0, 1, 2, 3, 4])
                source_ip = rng.choice(NORMAL_IPS)

            event_time = date.replace(hour=hour, minute=5)
            rows.append({
                "user_id": user_id,
                "event_time": event_time.isoformat(),
                "event_type": "login_success",
                "source_ip": source_ip,
                "scenario": scenario,
            })

    rows.sort(key=lambda row: (row["user_id"], row["event_time"]))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "user_id", "event_time", "event_type",
                "source_ip", "scenario",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    counts = Counter(row["scenario"] for row in rows)
    print(f"Generated {len(rows)} synthetic events.")
    print(f"Normal events: {counts['normal']}")
    print(f"Unfamiliar IP anomalies: {counts['unfamiliar_ip']}")
    print(f"Unusual-hour anomalies: {counts['unusual_hour']}")
    print(f"Total labeled anomalies: {len(rows) - counts['normal']}")
    print(f"Output: {OUTPUT}")


if __name__ == "__main__":
    main()
