# tests/test_output.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import Trip, Day, Event, Photo, Location, Expense
from post_trip_summary.output.detailed_record import generate_detailed_record
from post_trip_summary.output.shareable_pdf import compute_stats, select_highlights
from post_trip_summary.output.photo_prep import collect_highlight_photos, prepare_photos


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


def test_prepare_photos_copies_trip_story_fallback_photos_without_copying_all_kept(tmp_path):
    from PIL import Image

    highlight_path = tmp_path / "highlight.jpg"
    fallback_path = tmp_path / "fallback.jpg"
    unused_path = tmp_path / "unused.jpg"
    removed_path = tmp_path / "removed.jpg"
    for path in (highlight_path, fallback_path, unused_path, removed_path):
        Image.new("RGB", (10, 10), color="red").save(path)

    loc = Location(lat=48.858, lon=2.294, name="Eiffel Tower", address=None, city="Paris", country="France")
    highlighted_photos = [
        Photo(path=highlight_path, timestamp=datetime(2026, 3, 5, 16, 0), gps=None, is_highlight=True),
        Photo(path=unused_path, timestamp=datetime(2026, 3, 5, 16, 5), gps=None, is_highlight=False),
        Photo(path=removed_path, timestamp=datetime(2026, 3, 5, 16, 10), gps=None, is_highlight=False, is_kept=False),
    ]
    fallback_photos = [
        Photo(path=fallback_path, timestamp=datetime(2026, 3, 5, 17, 0), gps=None, is_highlight=False),
    ]
    event = Event(id="day01-event01", type="landmark", name="Eiffel Tower",
                  time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
                  location=loc, photos=highlighted_photos, description="", notes="", sources=["exif"])
    fallback_event = Event(id="day01-event02", type="walk", name="Walk",
                           time_range=(datetime(2026, 3, 5, 17, 0), datetime(2026, 3, 5, 18, 0)),
                           location=loc, photos=fallback_photos, description="", notes="", sources=["exif"])
    trip = Trip(name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 5)),
                days=[Day(date=date(2026, 3, 5), events=[event, fallback_event])])

    prepare_photos(trip, tmp_path / "output")

    assert (tmp_path / "output" / "photos" / "highlight.jpg").exists()
    assert (tmp_path / "output" / "photos" / "fallback.jpg").exists()
    assert not (tmp_path / "output" / "photos" / "unused.jpg").exists()
    assert not (tmp_path / "output" / "photos" / "removed.jpg").exists()
