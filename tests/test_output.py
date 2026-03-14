# tests/test_output.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import Trip, Day, Event, Photo, Location, Expense
from post_trip_summary.output.detailed_record import generate_detailed_record
from post_trip_summary.output.shareable_pdf import compute_stats, select_highlights
from post_trip_summary.output.photo_prep import collect_highlight_photos


def _trip() -> Trip:
    loc = Location(lat=48.858, lon=2.294, name="Eiffel Tower", address=None, city="Paris", country="France")
    photo = Photo(path=Path("/photos/img001.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294), is_highlight=True, ai_description="Eiffel Tower view")
    event = Event(id="day01-event01", type="landmark", name="Eiffel Tower",
                  time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
                  location=loc, photos=[photo], description="Visit to Eiffel Tower", notes="Amazing!", sources=["exif", "itinerary"])
    return Trip(
        name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 7)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
        expenses=[Expense(date=date(2026, 3, 5), amount=87.5, currency="EUR", merchant="Cafe", source="credit_card")],
    )


def test_generate_detailed_record(tmp_path):
    trip = _trip()
    output_path = tmp_path / "record.html"
    generate_detailed_record(trip, output_path)
    assert output_path.exists()
    content = output_path.read_text()
    assert "Paris 2026" in content
    assert "Eiffel Tower" in content


def test_compute_stats():
    trip = _trip()
    stats = compute_stats(trip)
    assert stats["days"] == 3
    assert stats["photos"] == 1
    assert stats["events"] == 1


def test_select_highlights_top_events():
    trip = _trip()
    highlights = select_highlights(trip, max_count=10)
    assert len(highlights) >= 1
    assert highlights[0].name == "Eiffel Tower"


def test_collect_highlight_photos():
    trip = _trip()
    photos = collect_highlight_photos(trip)
    assert len(photos) == 1
    assert photos[0].is_highlight
