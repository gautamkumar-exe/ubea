"""Read-only, privacy-preserving dataset snapshots for offline ML experiments."""
from __future__ import annotations

import csv
import hashlib
import hmac
import ipaddress
import json
import math
import os
import re
import tempfile
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path
from typing import Iterable

from app.services.ml_anomaly import FEATURE_NAMES

FEATURE_SCHEMA_VERSION = "ueba-seven-v1"
CSV_FIELDS = (
    "event_key", "subject_key", "subject_type", "user_key", "entity_key", "source_key", "external_key",
    "event_type_key", "source_ip_key", "event_time_utc", "feature_status",
    *FEATURE_NAMES, "split",
)


@dataclass(frozen=True)
class SnapshotOptions:
    cutoff: datetime
    hmac_key: bytes
    key_id: str = "local-v1"
    source_environment: str = "unclassified"

    def __post_init__(self) -> None:
        if not _aware(self.cutoff):
            raise ValueError("cutoff must be timezone-aware")
        if not isinstance(self.hmac_key, bytes) or len(self.hmac_key) < 32:
            raise ValueError("HMAC key must contain at least 32 bytes")
        if not isinstance(self.key_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", self.key_id
        ):
            raise ValueError("HMAC key ID must be 1-64 safe ASCII characters")
        if not isinstance(self.source_environment, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", self.source_environment
        ):
            raise ValueError("source environment must be 1-64 safe ASCII characters")


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def _token(key: bytes, namespace: str, value: object) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return hmac.new(key, f"{namespace}\0{raw}".encode(), hashlib.sha256).hexdigest()


def _canonical_ip(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return ipaddress.ip_address(value.strip()).compressed
    except ValueError:
        return None


def _identity(event: object) -> tuple[str, str | None]:
    user_id = getattr(event, "user_id", None)
    if isinstance(user_id, str) and user_id.strip():
        return "user", user_id.strip()
    entity_id = getattr(event, "entity_id", None)
    if isinstance(entity_id, str) and entity_id.strip():
        return "entity", entity_id.strip()
    return "", None


def _dedup_key(event: object) -> tuple[str, str] | None:
    source, external_id = getattr(event, "source", None), getattr(event, "external_id", None)
    if not isinstance(source, str) or not source.strip() or not isinstance(external_id, str) or not external_id.strip():
        return None
    return source.strip(), external_id.strip()


def _timestamp(event: object) -> datetime | None:
    value = getattr(event, "event_time", None)
    return _utc(value) if _aware(value) else None


def _stable_record_key(event: object, key: bytes) -> str:
    event_id = getattr(event, "id", None)
    if event_id is not None:
        return _token(key, "event-id", event_id) or ""
    identity = _dedup_key(event)
    if identity:
        return _token(key, "event-dedup", "\0".join(identity)) or ""
    values = [getattr(event, name, None) for name in ("source", "external_id", "user_id", "entity_id", "event_type", "source_ip")]
    ts = _timestamp(event)
    values.append(ts.isoformat() if ts else None)
    return _token(key, "event-fallback", json.dumps(values)) or ""


def _deduplicate(events: Iterable[object], key: bytes) -> tuple[list[object], int]:
    valid, invalid = [], []
    for event in events:
        ts = _timestamp(event)
        (valid if ts else invalid).append((ts, _stable_record_key(event, key), event))
    valid.sort(key=lambda item: (item[0], item[1]))
    invalid.sort(key=lambda item: item[1])
    seen: set[tuple[str, str]] = set()
    result, duplicates = [], 0
    for _, _, event in valid + invalid:
        identity = _dedup_key(event)
        if identity and identity in seen:
            duplicates += 1
            continue
        if identity:
            seen.add(identity)
        result.append(event)
    return result, duplicates


def _split_cutoffs(events: list[object]) -> tuple[datetime | None, datetime | None]:
    timestamps = sorted({_timestamp(event) for event in events if _timestamp(event)})
    if not timestamps:
        return None, None
    train_i = max(0, min(len(timestamps) - 1, math.ceil(len(timestamps) * 0.70) - 1))
    val_i = max(train_i, min(len(timestamps) - 1, math.ceil(len(timestamps) * 0.85) - 1))
    return timestamps[train_i], timestamps[val_i]


def _split_for(event_time: datetime | None, cutoffs: tuple[datetime | None, datetime | None]) -> str:
    if event_time is None:
        return "unassigned_invalid_time"
    train_end, validation_end = cutoffs
    if train_end is None or validation_end is None or event_time <= train_end:
        return "train"
    if event_time <= validation_end:
        return "validation"
    return "test"


def _feature_rows(events: list[object]) -> tuple[dict[int, dict[str, object]], int]:
    valid = [event for event in events if _timestamp(event)]
    valid.sort(key=lambda event: (_timestamp(event), str(getattr(event, "id", ""))))
    histories: dict[str, dict[str, object]] = defaultdict(
        lambda: {"times": deque(), "types": set(), "ips": Counter()}
    )
    rows: dict[int, dict[str, object]] = {}
    invalid_values = 0
    for timestamp, same_time in groupby(valid, key=_timestamp):
        assert timestamp is not None
        batch = list(same_time)
        for event in batch:
            uid = getattr(event, "user_id", None)
            uid = uid.strip() if isinstance(uid, str) else ""
            event_type = getattr(event, "event_type", None)
            event_type = event_type.strip() if isinstance(event_type, str) else ""
            ip = _canonical_ip(getattr(event, "source_ip", None))
            history = histories[uid] if uid else None
            if history is not None:
                recent: deque[datetime] = history["times"]
                while recent and recent[0] < timestamp - timedelta(hours=24):
                    recent.popleft()
                types: set[str] = history["types"]
                ips: Counter[str] = history["ips"]
            else:
                recent, types, ips = deque(), set(), Counter()
            hour = timestamp.hour + timestamp.minute / 60 + timestamp.second / 3600
            angle = 2 * math.pi * hour / 24
            features: list[float | None] = [
                math.sin(angle), math.cos(angle),
                float("login" in event_type.lower()) if event_type else None,
                float(ip in ips) if ip and uid else None,
                float(event_type in types) if event_type and uid else None,
                math.log1p(len(recent)) if uid else None,
                math.log1p(ips[ip]) if ip and uid else None,
            ]
            if not event_type:
                invalid_values += 1
            invalid_values += sum(
                value is not None and not math.isfinite(value) for value in features
            )
            status = "valid"
            if not event_type:
                status = "invalid_event_type"
            elif not uid:
                status = "partial_missing_user"
            elif not ip:
                status = "partial_missing_or_invalid_ip"
            rows[id(event)] = {"features": features, "feature_status": status}
        # Equal-time records have no reliable ordering; none can influence a peer.
        for event in batch:
            uid = getattr(event, "user_id", None)
            uid = uid.strip() if isinstance(uid, str) else ""
            if not uid:
                continue
            history = histories[uid]
            event_type = getattr(event, "event_type", None)
            event_type = event_type.strip() if isinstance(event_type, str) else ""
            ip = _canonical_ip(getattr(event, "source_ip", None))
            history["times"].append(timestamp)
            if event_type:
                history["types"].add(event_type)
            if ip:
                history["ips"][ip] += 1
    return rows, invalid_values


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    import io
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def build_snapshot(events: Iterable[object], options: SnapshotOptions) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Build deterministic sanitized rows and aggregate metadata."""
    cutoff = _utc(options.cutoff)
    supplied = list(events)
    at_cutoff = [event for event in supplied if _timestamp(event) is None or _timestamp(event) <= cutoff]
    deduped, duplicate_count = _deduplicate(at_cutoff, options.hmac_key)
    features, invalid_feature_values = _feature_rows(deduped)
    split_cutoffs = _split_cutoffs(deduped)
    rows, missing = [], Counter()
    entity_keys: set[str] = set()
    time_values: list[datetime] = []
    split_counts = Counter()
    for event in deduped:
        kind, identity = _identity(event)
        user = getattr(event, "user_id", None)
        source = getattr(event, "source", None)
        ext_id = getattr(event, "external_id", None)
        event_type = getattr(event, "event_type", None)
        ip = _canonical_ip(getattr(event, "source_ip", None))
        ts = _timestamp(event)
        feature = features.get(id(event), {})
        values = feature.get("features", [None] * len(FEATURE_NAMES))
        split = _split_for(ts, split_cutoffs)
        split_counts[split] += 1
        row: dict[str, object] = {
            "event_key": _stable_record_key(event, options.hmac_key),
            "subject_key": _token(
                options.hmac_key,
                f"subject:{kind}" if kind else "subject:untyped",
                identity,
            ),
            "subject_type": kind or None,
            "user_key": _token(options.hmac_key, "user", user),
            "entity_key": _token(options.hmac_key, "entity", getattr(event, "entity_id", None)),
            "source_key": _token(options.hmac_key, "source", source),
            "external_key": _token(options.hmac_key, "external-id", ext_id),
            "event_type_key": _token(options.hmac_key, "event-type", event_type),
            "source_ip_key": _token(options.hmac_key, "source-ip", ip),
            "event_time_utc": ts.isoformat() if ts else None,
            "feature_status": feature.get("feature_status", "invalid_timestamp"),
            "split": split,
        }
        for name, value in zip(FEATURE_NAMES, values):
            row[name] = value
            if value is None:
                missing[name] += 1
        for field in ("subject_key", "user_key", "entity_key", "source_key", "external_key", "event_type_key", "source_ip_key", "event_time_utc"):
            if row[field] is None:
                missing[field] += 1
        if row["entity_key"]:
            entity_keys.add(str(row["entity_key"]))
        elif row["subject_key"]:
            entity_keys.add(str(row["subject_key"]))
        if ts:
            time_values.append(ts)
        rows.append(row)
    rows.sort(key=lambda row: (row["event_time_utc"] or "", row["event_key"]))
    csv_data = _csv_bytes(rows)
    snapshot_id = hashlib.sha256(
        (
            FEATURE_SCHEMA_VERSION
            + "\0"
            + options.key_id
            + "\0"
            + options.source_environment.lower()
            + "\0"
            + cutoff.isoformat()
            + "\0"
        ).encode()
        + csv_data
    ).hexdigest()
    metadata: dict[str, object] = {
        "snapshot_id": snapshot_id,
        "snapshot_version": "1",
        "pipeline_version": "offline-dataset-snapshot-v1",
        "pseudonymization_key_id": options.key_id,
        "source_environment": options.source_environment.lower(),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "source_model": "app.models.security_event.SecurityEvent",
        "source_selection": "security_events where event_time <= inclusive cutoff; ordered by event_time and primary key",
        "source_read_only": True,
        "cutoff_utc": cutoff.isoformat(),
        "records_processed": len(supplied),
        "records_at_or_before_cutoff": sum(
            1 for event in supplied if _timestamp(event) is not None and _timestamp(event) <= cutoff
        ),
        "records_without_comparable_timestamp": sum(
            1 for event in supplied if _timestamp(event) is None
        ),
        "records_in_snapshot": len(rows),
        "duplicate_records_removed": duplicate_count,
        "invalid_timestamps": sum(_timestamp(event) is None for event in deduped),
        "invalid_feature_values": invalid_feature_values,
        "missing_values": dict(sorted(missing.items())),
        "entity_coverage": len(entity_keys),
        "temporal_coverage_utc": {"start": min(time_values).isoformat() if time_values else None, "end": max(time_values).isoformat() if time_values else None},
        "labels": {"status": "unavailable_no_verified_event_label_source", "unlabeled_records": len(rows), "class_distribution": None},
        "split_counts": dict(sorted(split_counts.items())),
        "split_cutoffs_utc": {"train_end": split_cutoffs[0].isoformat() if split_cutoffs[0] else None, "validation_end": split_cutoffs[1].isoformat() if split_cutoffs[1] else None},
        "split_policy": "chronological unique-timestamp 70/15/15; timestamp ties stay together",
        "entity_split_note": "Entities may appear across chronological partitions for known-entity future prediction. Use separate entity-held-out evaluation to claim unseen-entity generalization.",
        "privacy": {"identifiers": "namespace-separated HMAC-SHA256 pseudonyms", "source_ip": "validated and HMAC-SHA256 pseudonymized", "raw_event": "excluded", "key_material_in_output": False},
        "feature_names": list(FEATURE_NAMES),
        "unavailable_features": ["authentication_outcome", "device_or_process_context", "user_local_timezone", "point_in_time_saved_baseline_deviations", "verified_event_label"],
    }
    return rows, metadata


def _atomic_write(path: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temp.write(content)
        temp.flush()
        os.fsync(temp.fileno())
        temp_path = Path(temp.name)
    temp_path.replace(path)


def write_snapshot(events: Iterable[object], options: SnapshotOptions, output_dir: Path) -> dict[str, object]:
    rows, metadata = build_snapshot(events, options)
    snapshot_id = str(metadata["snapshot_id"])
    destination = output_dir / snapshot_id
    destination.mkdir(parents=True, exist_ok=True)
    _atomic_write(destination / "dataset.csv", _csv_bytes(rows))
    _atomic_write(destination / "manifest.json", (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode())
    cutoffs = metadata["split_cutoffs_utc"]
    counts = metadata["split_counts"]
    splits = {
        "snapshot_id": snapshot_id,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "partitions": {
            "train": {"end_utc": cutoffs["train_end"], "records": counts.get("train", 0)},
            "validation": {"end_utc": cutoffs["validation_end"], "records": counts.get("validation", 0)},
            "test": {"after_utc": cutoffs["validation_end"], "records": counts.get("test", 0)},
            "unassigned_invalid_time": {"records": counts.get("unassigned_invalid_time", 0)},
        },
        "policy": metadata["split_policy"],
    }
    _atomic_write(destination / "splits.json", (json.dumps(splits, indent=2, sort_keys=True) + "\n").encode())
    return {**metadata, "output_directory": str(destination)}
