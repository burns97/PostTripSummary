# tests/test_ingest_dayone.py
import json
from datetime import datetime
from pathlib import Path
from post_trip_summary.pipeline.ingest.dayone import ingest_dayone


def _write_dayone_export(path: Path) -> None:
    data = {
        "entries": [
            {
                "creationDate": "2026-03-05T18:30:00Z",
                "text": "Visited the Eiffel Tower today. Amazing views!",
                "location": {"latitude": 48.8584, "longitude": 2.2945, "placeName": "Eiffel Tower"},
                "photos": [{"identifier": "abc123", "md5": "def456", "type": "jpeg"}],
            },
            {
                "creationDate": "2026-03-06T12:00:00Z",
                "text": "Lunch at a great bistro near the Seine.",
            },
        ]
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_parse_entries(tmp_path):
    export_path = tmp_path / "dayone.json"
    _write_dayone_export(export_path)
    result = ingest_dayone(export_path)
    assert len(result) == 2


def test_entry_with_location(tmp_path):
    export_path = tmp_path / "dayone.json"
    _write_dayone_export(export_path)
    result = ingest_dayone(export_path)
    entry = result[0]
    assert entry["text"] == "Visited the Eiffel Tower today. Amazing views!"
    assert abs(entry["lat"] - 48.8584) < 0.001
    assert entry["place_name"] == "Eiffel Tower"


def test_entry_without_location(tmp_path):
    export_path = tmp_path / "dayone.json"
    _write_dayone_export(export_path)
    result = ingest_dayone(export_path)
    entry = result[1]
    assert entry["lat"] is None
    assert entry["lon"] is None


def test_entry_photos(tmp_path):
    export_path = tmp_path / "dayone.json"
    _write_dayone_export(export_path)
    result = ingest_dayone(export_path)
    assert len(result[0]["photo_ids"]) == 1
    assert result[1]["photo_ids"] == []
