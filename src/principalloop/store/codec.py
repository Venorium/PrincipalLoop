"""Versioned encoding of domain values; never pickle or eval."""

from dataclasses import asdict, fields
from datetime import datetime
import json

from ..domain.types import Decision, Kind, Mode, Plan, Status, Trajectory, Utility
from .errors import StoreError


def values(value):
    def convert(item):
        if isinstance(item, datetime):
            return item.isoformat()
        if isinstance(item, dict):
            return {key: convert(val) for key, val in item.items()}
        if isinstance(item, (tuple, list)):
            return [convert(val) for val in item]
        return item
    return convert(asdict(value))


def encode(value) -> str:
    return json.dumps({"storage_version": 1, "value": values(value)}, sort_keys=True, separators=(",", ":"))


def decode(raw: str, kind):
    try:
        envelope = json.loads(raw)
        if set(envelope) != {"storage_version", "value"} or type(envelope["storage_version"]) is not int or envelope["storage_version"] != 1:
            raise ValueError("Unsupported stored value version")
        data = envelope["value"]
        if not isinstance(data, dict) or set(data) != {field.name for field in fields(kind)}:
            raise ValueError("Stored value fields do not match the storage version")
        if kind is Plan:
            data["mode"] = Mode(data["mode"])
            data["scopes"] = tuple((name, Trajectory(state)) for name, state in data["scopes"])
        elif kind is Decision:
            for key, enum in (("kind", Kind), ("status", Status), ("utility", Utility)):
                data[key] = enum(data[key])
            for key in ("expires_at", "defer_until"):
                if data[key] is not None:
                    data[key] = datetime.fromisoformat(data[key])
            for key in ("scope", "evidence_ids"):
                data[key] = tuple(data[key])
        else:
            raise ValueError("Unknown stored type")
        return kind(**data)
    except (ValueError, TypeError, KeyError) as error:
        raise StoreError("STATE_INVALID", "Stored domain state is invalid or unsupported") from error
