# tests/test_serialization.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Transit, TransitPoint,
    Accommodation, Expense,
)
from post_trip_summary.serialization import trip_to_json, trip_from_json


def _make_sample_trip() -> Trip:
    loc = Location(lat=48.8584, lon=2.2945, name="Eiffel Tower", address=None, city="Paris", country="France")
    photo = Photo(path=Path("/photos/img001.jpg"), timestamp=datetime(2026, 3, 5, 16, 30), gps=(48.8584, 2.2945), is_highlight=True, ai_description="Family at Eiffel Tower")
    event = Event(id="day01-event01", type="landmark", name="Eiffel Tower", time_range=(datetime(2026, 3, 5, 16, 15), datetime(2026, 3, 5, 18, 0)), location=loc, photos=[photo], description="Visit", notes="Great view", sources=["exif"])
    day = Day(date=date(2026, 3, 5), events=[event])
    dep_loc = Location(lat=49.0, lon=2.5, name="CDG", address=None, city="Paris", country="France")
    arr_loc = Location(lat=48.8, lon=2.3, name="Hotel", address="123 Rue", city="Paris", country="France")
    transit = Transit(mode="taxi", departure=TransitPoint(location=dep_loc, time=datetime(2026, 3, 5, 14, 0), name="CDG T2"), arrival=TransitPoint(location=arr_loc, time=datetime(2026, 3, 5, 15, 0), name="Hotel"), details={"cost": 55}, sources=["itinerary"])
    accom = Accommodation(name="Hotel Le Marais", location=arr_loc, check_in=date(2026, 3, 5), check_out=date(2026, 3, 8), sources=["itinerary"])
    expense = Expense(date=date(2026, 3, 5), amount=87.5, currency="EUR", merchant="REST LE PETIT", category="dining", event_id="day01-event04", source="credit_card")
    return Trip(name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 12)), days=[day], accommodations=[accom], transits=[transit], expenses=[expense])


def test_round_trip_serialization():
    trip = _make_sample_trip()
    json_str = trip_to_json(trip)
    restored = trip_from_json(json_str)
    assert restored.name == trip.name
    assert restored.date_range == trip.date_range
    assert len(restored.days) == 1
    assert len(restored.days[0].events) == 1
    assert restored.days[0].events[0].id == "day01-event01"
    assert restored.days[0].events[0].photos[0].gps == (48.8584, 2.2945)
    assert restored.days[0].events[0].photos[0].path == Path("/photos/img001.jpg")
    assert len(restored.transits) == 1
    assert restored.transits[0].mode == "taxi"
    assert len(restored.accommodations) == 1
    assert len(restored.expenses) == 1
    assert restored.expenses[0].amount == 87.5


def test_serialization_to_file(tmp_path):
    from post_trip_summary.serialization import save_trip, load_trip
    trip = _make_sample_trip()
    path = tmp_path / "trip.json"
    save_trip(trip, path)
    assert path.exists()
    restored = load_trip(path)
    assert restored.name == "Paris 2026"
