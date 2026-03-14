# tests/test_review_skeleton.py
from datetime import date, datetime
from post_trip_summary.models import Trip, Day, Event, Location
from post_trip_summary.pipeline.review_skeleton import format_day_summary, format_event_line


def _event(id: str, type: str, name: str, start: str, end: str) -> Event:
    return Event(
        id=id, type=type, name=name,
        time_range=(datetime.fromisoformat(start), datetime.fromisoformat(end)),
        location=Location(lat=0, lon=0, name=name, address=None, city="Paris", country="France"),
        photos=[],
        description="",
        notes="",
        sources=["exif"],
    )


def test_format_event_line_landmark():
    event = _event("day01-event01", "landmark", "Eiffel Tower", "2026-03-05 16:15:00", "2026-03-05 18:00:00")
    line = format_event_line(event, index=1)
    assert "Eiffel Tower" in line
    assert "4:15 PM" in line or "16:15" in line


def test_format_event_line_restaurant():
    event = _event("day01-event02", "restaurant", "REST LE PETIT", "2026-03-05 19:30:00", "2026-03-05 20:30:00")
    line = format_event_line(event, index=2)
    assert "REST LE PETIT" in line


def test_format_event_line_transit():
    event = _event("day01-event03", "transit", "Flight: JFK -> CDG", "2026-03-05 08:00:00", "2026-03-05 14:00:00")
    line = format_event_line(event, index=3)
    assert "JFK" in line


def test_format_day_summary():
    events = [
        _event("day01-event01", "transit", "Flight: JFK -> CDG", "2026-03-05 08:00:00", "2026-03-05 14:00:00"),
        _event("day01-event02", "hotel", "Hotel Le Marais", "2026-03-05 15:30:00", "2026-03-05 16:00:00"),
    ]
    day = Day(date=date(2026, 3, 5), events=events)
    summary = format_day_summary(day, day_num=1)
    assert "Day 1" in summary
    assert "March 5" in summary or "Mar" in summary
