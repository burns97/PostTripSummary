# tests/test_models.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Transit, TransitPoint,
    Accommodation, Expense,
)


def test_create_location():
    loc = Location(lat=48.8584, lon=2.2945, name="Eiffel Tower", address="5 Av. Anatole France", city="Paris", country="France")
    assert loc.name == "Eiffel Tower"
    assert loc.lat == 48.8584


def test_create_photo():
    photo = Photo(path=Path("/photos/img001.jpg"), timestamp=datetime(2026, 3, 5, 14, 30), gps=(48.8584, 2.2945), is_highlight=False, ai_description=None)
    assert photo.gps == (48.8584, 2.2945)
    assert photo.is_highlight is False


def test_create_event():
    loc = Location(lat=48.8584, lon=2.2945, name="Eiffel Tower", address=None, city="Paris", country="France")
    event = Event(
        id="day01-event01",
        type="landmark",
        name="Eiffel Tower",
        time_range=(datetime(2026, 3, 5, 16, 15), datetime(2026, 3, 5, 18, 0)),
        location=loc,
        photos=[],
        description="Visit to the Eiffel Tower",
        notes="",
        sources=["exif", "itinerary"],
    )
    assert event.id == "day01-event01"
    assert event.type == "landmark"
    assert len(event.sources) == 2


def test_create_transit():
    dep = TransitPoint(
        location=Location(lat=49.0097, lon=2.5479, name="CDG", address=None, city="Paris", country="France"),
        time=datetime(2026, 3, 5, 14, 0),
        name="CDG Terminal 2",
    )
    arr = TransitPoint(
        location=Location(lat=48.8566, lon=2.3522, name="Hotel", address=None, city="Paris", country="France"),
        time=datetime(2026, 3, 5, 15, 30),
        name="Hotel Le Marais",
    )
    transit = Transit(mode="taxi", departure=dep, arrival=arr, details={"cost": "€55"}, sources=["itinerary"])
    assert transit.mode == "taxi"


def test_create_expense():
    exp = Expense(date=date(2026, 3, 5), amount=87.50, currency="EUR", merchant="REST LE PETIT", category="dining", event_id="day01-event04", source="credit_card")
    assert exp.amount == 87.50
    assert exp.event_id == "day01-event04"


def test_create_trip():
    trip = Trip(name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 12)), days=[], accommodations=[], transits=[], expenses=[])
    assert trip.name == "Paris 2026"
    assert trip.days == []
