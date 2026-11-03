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
from app.models.security_event import SecurityEvent
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
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
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

    hmac_secret = os.environ.get("UEBA_SNAPSHOT_HMAC_KEY", "")
    if len(hmac_secret.encode("utf-8")) < 32:
        parser.error("UEBA_SNAPSHOT_HMAC_KEY must be set to at least 32 bytes")
    try:
        events = _read_events_read_only(settings.database_url, args.cutoff)
        summary = write_snapshot(events, SnapshotOptions(args.cutoff, hmac_secret.encode()), args.output_dir)
    except Exception:
        # Do not print database exception text; drivers can include parameter data.
        print("Dataset snapshot failed. Check database connectivity, permissions, and local configuration.", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
