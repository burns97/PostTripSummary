# tests/test_preview.py
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from post_trip_summary.models import Trip, Day, Event, Photo, Location
from post_trip_summary.preview.server import create_app


def _trip() -> Trip:
    loc = Location(lat=48.858, lon=2.294, name="Eiffel Tower", address=None, city="Paris", country="France")
    photo = Photo(path=Path("/photos/img001.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294), is_highlight=True, ai_description="Tower")
    event = Event(id="d1e1", type="landmark", name="Eiffel Tower",
                  time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
                  location=loc, photos=[photo], description="Visit", notes="", sources=["exif"])
    return Trip(name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 7)),
                days=[Day(date=date(2026, 3, 5), events=[event])])


def test_preview_detailed_record():
    trip = _trip()
    app = create_app(trip)
    client = TestClient(app)
    response = client.get("/detailed")
    assert response.status_code == 200
    assert "Paris 2026" in response.text


def test_preview_summary():
    trip = _trip()
    app = create_app(trip)
    client = TestClient(app)
    response = client.get("/summary")
    assert response.status_code == 200
