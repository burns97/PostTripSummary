# tests/test_skeleton.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import (
    Photo, Location, Accommodation, Transit, TransitPoint, Expense, Event, Day, Trip,
)
from post_trip_summary.pipeline.skeleton import (
    build_skeleton, _match_cluster_to_itinerary, _match_cluster_to_expense,
    _classify_event, _assign_event_ids,
)


def _photo(ts: str, lat: float, lon: float) -> Photo:
    return Photo(path=Path(f"/p/{ts}.jpg"), timestamp=datetime.fromisoformat(ts), gps=(lat, lon))


def _make_cluster(ts_start: str, ts_end: str, lat: float, lon: float, count: int = 5) -> dict:
    return {
        "photos": [_photo(ts_start, lat, lon)] * count,
        "centroid": (lat, lon),
        "time_range": (datetime.fromisoformat(ts_start), datetime.fromisoformat(ts_end)),
    }


def test_match_cluster_to_accommodation():
    cluster = _make_cluster("2026-03-05 15:30:00", "2026-03-05 16:00:00", 48.857, 2.362)
    acc = Accommodation(
        name="Hotel Le Marais",
        location=Location(lat=48.857, lon=2.362, name="Hotel Le Marais", address="123 Rue", city="Paris", country="France"),
        check_in=date(2026, 3, 5),
        check_out=date(2026, 3, 8),
        sources=["itinerary"],
    )
    match = _match_cluster_to_itinerary(cluster, [acc], [])
    assert match is not None
    assert match["name"] == "Hotel Le Marais"
    assert match["type"] == "hotel"


def test_match_cluster_to_expense():
    cluster = _make_cluster("2026-03-05 19:00:00", "2026-03-05 19:30:00", 48.858, 2.294)
    expenses = [
        Expense(date=date(2026, 3, 5), amount=87.5, currency="EUR", merchant="REST LE PETIT", category="dining", source="credit_card"),
    ]
    match = _match_cluster_to_expense(cluster, expenses)
    assert match is not None
    assert match.merchant == "REST LE PETIT"


def test_classify_event_restaurant():
    assert _classify_event(expense_category="dining") == "restaurant"


def test_classify_event_unknown():
    assert _classify_event() == "unknown"


def test_assign_event_ids():
    events = [
        Event(id="", type="landmark", name="A", time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 11, 0)),
              location=Location(lat=0, lon=0, name="", address=None, city="", country="")),
        Event(id="", type="restaurant", name="B", time_range=(datetime(2026, 3, 5, 12, 0), datetime(2026, 3, 5, 13, 0)),
              location=Location(lat=0, lon=0, name="", address=None, city="", country="")),
    ]
    days = [Day(date=date(2026, 3, 5), events=events)]
    _assign_event_ids(days)
    assert days[0].events[0].id == "day01-event01"
    assert days[0].events[1].id == "day01-event02"


def test_build_skeleton_basic():
    photos = [
        _photo("2026-03-05 10:00:00", 48.858, 2.294),
        _photo("2026-03-05 10:05:00", 48.858, 2.295),
    ]
    trip_data = {
        "photos": photos,
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    trip = build_skeleton(trip_data, gap_minutes=15, distance_meters=200)
    assert isinstance(trip, Trip)
    assert len(trip.days) >= 1
    assert len(trip.days[0].events) >= 1
