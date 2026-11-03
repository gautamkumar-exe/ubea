"""Create an offline sanitized dataset snapshot from the event database.

Run from backend with: python -m scripts.prepare_ml_dataset --cutoff ...
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.services.ml_dataset import SnapshotOptions, write_snapshot

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "data" / "ml_snapshots"


def _parse_datetime(value: str) -> datetime:
    try:
        cutoff = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("cutoff must be an ISO-8601 datetime") from exc
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise argparse.ArgumentTypeError("cutoff must include a timezone")
    return cutoff


def _read_events_read_only(database_url: str, cutoff: datetime) -> list[SecurityEvent]:
    if not database_url.startswith("postgresql"):
        raise ValueError("offline snapshot CLI requires PostgreSQL to enforce read-only transactions")
    # Delay model imports until after configuration validation. Importing the
    # application model package creates its normal engine and would otherwise
    # fail before the CLI can report a missing DATABASE_URL clearly.
    from app.models.security_event import SecurityEvent

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        # Keep loaded values available after the read-only transaction closes;
        # the snapshot transform runs on these detached, in-memory rows.
        with Session(engine, expire_on_commit=False) as session:
            with session.begin():
                session.execute(text("SET TRANSACTION READ ONLY"))
                statement = (
                    select(SecurityEvent)
                    .where(SecurityEvent.event_time <= cutoff)
                    .order_by(SecurityEvent.event_time.asc(), SecurityEvent.id.asc())
                    .execution_options(yield_per=1000)
                )
                return list(session.scalars(statement).all())
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cutoff", required=True, type=_parse_datetime, help="inclusive ISO-8601 event-time cutoff")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    database_url = settings.database_url.strip()
    if not database_url or "change_me_local_only" in database_url:
        print(
            "DATABASE_URL is not configured. Set it to an isolated PostgreSQL database URL.",
            file=sys.stderr,
        )
        return 2
    if not database_url.startswith("postgresql"):
        print("DATABASE_URL must use PostgreSQL for read-only transaction enforcement.", file=sys.stderr)
        return 2
    environment = os.environ.get("ENVIRONMENT", "").strip().lower()
    if environment not in {"development", "test"} or settings.environment.lower() != environment:
        print(
            "Set ENVIRONMENT explicitly to development or test for offline snapshot preparation.",
            file=sys.stderr,
        )
        return 2

    hmac_secret = os.environ.get("UEBA_SNAPSHOT_HMAC_KEY", "")
    secret_bytes = hmac_secret.encode("utf-8")
    if not hmac_secret:
        print("UEBA_SNAPSHOT_HMAC_KEY is not configured.", file=sys.stderr)
        return 2
    if len(secret_bytes) < 32:
        print("UEBA_SNAPSHOT_HMAC_KEY must contain at least 32 bytes.", file=sys.stderr)
        return 2
    key_id = os.environ.get("UEBA_SNAPSHOT_HMAC_KEY_ID", "local-v1")
    try:
        options = SnapshotOptions(
            args.cutoff,
            secret_bytes,
            key_id,
            environment,
        )
        events = _read_events_read_only(database_url, args.cutoff)
        summary = write_snapshot(events, options, args.output_dir)
    except ValueError as exc:
        # ValueError messages cover config shape only; none include secret data.
        print(f"Invalid snapshot configuration: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Do not print database exception text; drivers can include parameter data.
        print(
            f"Dataset snapshot failed ({type(exc).__name__}). Check database connectivity, read-only permissions, and local configuration.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
