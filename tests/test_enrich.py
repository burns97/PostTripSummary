# tests/test_enrich.py
from datetime import datetime, date
from pathlib import Path
from unittest.mock import patch, MagicMock
from post_trip_summary.models import Trip, Day, Event, Photo, Location
from post_trip_summary.vision.client import VisionResult
from post_trip_summary.pipeline.enrich import enrich_trip, _select_highlights


def _photo(name: str) -> Photo:
    return Photo(path=Path(f"/photos/{name}.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294))


def _event(name: str, sources: list[str], num_photos: int = 10) -> Event:
    return Event(
        id="day01-event01", type="unknown", name=name,
        time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
        location=Location(lat=48.858, lon=2.294, name=name, address=None, city="Paris", country="France"),
        photos=[_photo(f"img{i}") for i in range(num_photos)],
        description="", notes="", sources=sources,
    )


def test_select_highlights_default():
    photos = [_photo(f"img{i}") for i in range(20)]
    highlights = _select_highlights(photos, max_count=5)
    assert len(highlights) == 5
    assert all(p.is_highlight for p in highlights)


def test_select_highlights_fewer_than_max():
    photos = [_photo(f"img{i}") for i in range(3)]
    highlights = _select_highlights(photos, max_count=5)
    assert len(highlights) == 3


def test_enrich_applies_vision_results():
    """Mock the vision client and verify enrichment updates events."""
    event = _event("Unknown Place", sources=["exif"], num_photos=3)
    trip = Trip(
        name="Test", date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )

    mock_result = VisionResult(description="The Eiffel Tower", landmark="Eiffel Tower", confidence="high")

    with patch("post_trip_summary.pipeline.enrich.VisionClient") as MockClient, \
         patch("post_trip_summary.pipeline.enrich._read_image", return_value=(b"fakedata", "image/jpeg")):
        instance = MockClient.return_value
        instance.analyze.return_value = mock_result
        instance.estimate_cost.return_value = 0.01

        enriched = enrich_trip(trip, api_key="test", auto_approve=True)
        assert enriched.days[0].events[0].description == "The Eiffel Tower"
