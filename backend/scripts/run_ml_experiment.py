"""Run an offline Isolation Forest experiment; never connects to a database."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.ml_experiments import (
    ExperimentError,
    SnapshotValidationError,
    run_snapshot_experiment,
    run_synthetic_benchmark,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR.parent / "data" / "ml_experiments"
DEFAULT_FIXTURE = SCRIPT_DIR / "reports" / "synthetic_events.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--snapshot-dir", type=Path, help="directory containing dataset.csv, manifest.json, and splits.json")
    source.add_argument("--synthetic-benchmark", action="store_true", help="evaluate the checked-in synthetic scenario fixture")
    parser.add_argument(
        "--confirm-nonproduction",
        action="store_true",
        help="confirm that the snapshot contains no production records",
    )
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="synthetic fixture CSV path")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=100)
    args = parser.parse_args(argv)
    if args.snapshot_dir is not None and not args.confirm_nonproduction:
        parser.error("--confirm-nonproduction is required for snapshot training")

    try:
        options = {
            "contamination": args.contamination,
            "random_state": args.random_state,
            "n_estimators": args.n_estimators,
        }
        if args.synthetic_benchmark:
            result = run_synthetic_benchmark(args.fixture, args.output_dir, **options)
        else:
            result = run_snapshot_experiment(args.snapshot_dir, args.output_dir, **options)
    except (SnapshotValidationError, ExperimentError, ValueError) as exc:
        print(f"Experiment failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Do not print arbitrary exception details that could contain source data.
        print(f"Experiment failed ({type(exc).__name__}); see local experiment metadata.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
