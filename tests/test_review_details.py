# tests/test_review_details.py
from datetime import datetime
from pathlib import Path
from post_trip_summary.models import Event, Photo, Location
from post_trip_summary.pipeline.review_details import format_event_detail


def _photo(name: str, highlight: bool = False, desc: str | None = None) -> Photo:
    return Photo(path=Path(f"/photos/{name}.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294), is_highlight=highlight, ai_description=desc)


def test_format_event_detail():
    event = Event(
        id="day01-event01", type="landmark", name="Eiffel Tower",
        time_range=(datetime(2026, 3, 5, 16, 15), datetime(2026, 3, 5, 18, 0)),
        location=Location(lat=48.858, lon=2.294, name="Eiffel Tower", address=None, city="Paris", country="France"),
        photos=[
            _photo("img001", highlight=True, desc="Family at Eiffel Tower"),
            _photo("img002", highlight=True, desc="Tower from Trocadero"),
            _photo("img003", highlight=False),
        ],
        description="Visit to the Eiffel Tower",
        notes="",
        sources=["exif", "itinerary"],
    )
    output = format_event_detail(event)
    assert "Eiffel Tower" in output
    assert "Family at Eiffel Tower" in output
    assert "highlight" in output.lower() or "\u2605" in output
    assert "3 total" in output or "3" in output
