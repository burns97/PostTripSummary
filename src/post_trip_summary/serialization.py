# src/post_trip_summary/serialization.py
"""JSON serialization for Trip model tree."""
import json
from datetime import date, datetime
from pathlib import Path

from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Transit, TransitPoint,
    Accommodation, Expense,
)


def _encode(obj: object) -> object:
    """Recursively convert model tree to JSON-safe dicts."""
    if isinstance(obj, datetime):
        return {"__type__": "datetime", "value": obj.isoformat()}
    if isinstance(obj, date):
        return {"__type__": "date", "value": obj.isoformat()}
    if isinstance(obj, Path):
        return {"__type__": "Path", "value": str(obj)}
    if isinstance(obj, tuple):
        return {"__type__": "tuple", "value": [_encode(v) for v in obj]}
    if isinstance(obj, list):
        return [_encode(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        return {
            "__type__": type(obj).__name__,
            **{k: _encode(v) for k, v in obj.__dict__.items()},
        }
    return obj


_MODEL_MAP = {
    "Trip": Trip,
    "Day": Day,
    "Event": Event,
    "Photo": Photo,
    "Location": Location,
    "Transit": Transit,
    "TransitPoint": TransitPoint,
    "Accommodation": Accommodation,
    "Expense": Expense,
}


def _decode(obj: object) -> object:
    """Recursively restore model tree from JSON-safe dicts."""
    if isinstance(obj, list):
        return [_decode(v) for v in obj]
    if not isinstance(obj, dict):
        return obj
    type_tag = obj.get("__type__")
    if type_tag == "datetime":
        return datetime.fromisoformat(obj["value"])
    if type_tag == "date":
        return date.fromisoformat(obj["value"])
    if type_tag == "Path":
        return Path(obj["value"])
    if type_tag == "tuple":
        return tuple(_decode(v) for v in obj["value"])
    if type_tag in _MODEL_MAP:
        cls = _MODEL_MAP[type_tag]
        fields = {k: _decode(v) for k, v in obj.items() if k != "__type__"}
        return cls(**fields)
    return {k: _decode(v) for k, v in obj.items()}


# Public API for encoding/decoding arbitrary values (used by CLI for trip_data dict)
encode_value = _encode
decode_value = _decode


def trip_to_json(trip: Trip) -> str:
    return json.dumps(_encode(trip), indent=2)


def trip_from_json(json_str: str) -> Trip:
    return _decode(json.loads(json_str))


def save_trip(trip: Trip, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(trip_to_json(trip), encoding="utf-8")


def load_trip(path: Path) -> Trip:
    return trip_from_json(path.read_text(encoding="utf-8"))
