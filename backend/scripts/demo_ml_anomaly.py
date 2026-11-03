"""Run the offline four-scenario UEBA ML demonstration."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.ml_analytics import DEFAULT_FIXTURE, run_ml_analytics_demo


def run_demo(
    fixture_path: Path = DEFAULT_FIXTURE,
    *,
    contamination: float = 0.05,
    random_state: int = 42,
    n_estimators: int = 100,
) -> dict[str, object]:
    """Compatibility entry point used by the local demonstration and tests."""
    return run_ml_analytics_demo(
        fixture_path,
        contamination=contamination,
        random_state=random_state,
        n_estimators=n_estimators,
    )


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
