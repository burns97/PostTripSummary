# tests/test_ingest_google_maps.py
import json
from datetime import datetime
from pathlib import Path
from post_trip_summary.pipeline.ingest.google_maps import ingest_google_maps


def _write_timeline(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_parse_place_visits(tmp_path):
    timeline_path = tmp_path / "Records.json"
    _write_timeline(timeline_path, {
        "timelineObjects": [
            {
                "placeVisit": {
                    "location": {
                        "latitudeE7": 488584000,
                        "longitudeE7": 22945000,
                        "name": "Eiffel Tower",
                        "address": "5 Av. Anatole France, Paris",
                    },
                    "duration": {
                        "startTimestamp": "2026-03-05T16:15:00.000Z",
                        "endTimestamp": "2026-03-05T18:00:00.000Z",
                    },
                }
            }
        ]
    })
    result = ingest_google_maps(timeline_path)
    assert len(result["place_visits"]) == 1
    visit = result["place_visits"][0]
    assert visit["name"] == "Eiffel Tower"
    assert abs(visit["lat"] - 48.8584) < 0.001


def test_parse_activity_segments(tmp_path):
    timeline_path = tmp_path / "Records.json"
    _write_timeline(timeline_path, {
        "timelineObjects": [
            {
                "activitySegment": {
                    "startLocation": {"latitudeE7": 488584000, "longitudeE7": 22945000},
                    "endLocation": {"latitudeE7": 488660000, "longitudeE7": 23522000},
                    "duration": {
                        "startTimestamp": "2026-03-05T18:00:00.000Z",
                        "endTimestamp": "2026-03-05T18:30:00.000Z",
                    },
                    "activityType": "IN_VEHICLE",
                }
            }
        ]
    })
    result = ingest_google_maps(timeline_path)
    assert len(result["activity_segments"]) == 1


def test_empty_timeline(tmp_path):
    timeline_path = tmp_path / "Records.json"
    _write_timeline(timeline_path, {"timelineObjects": []})
    result = ingest_google_maps(timeline_path)
    assert result["place_visits"] == []
    assert result["activity_segments"] == []
