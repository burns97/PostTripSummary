import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from post_trip_summary.models import Day, Event, Location, Photo, Trip


def _photo(name: str) -> Photo:
    return Photo(
        path=Path(f"/photos/{name}.jpg"),
        timestamp=datetime(2026, 2, 19, 10, 0),
        gps=(-36.8485, 174.7633),
        is_kept=True,
    )


def _event(
    event_id: str,
    name: str,
    *,
    event_type: str,
    city: str,
    country: str,
    lat: float,
    lon: float,
) -> Event:
    return Event(
        id=event_id,
        type=event_type,
        name=name,
        time_range=(datetime(2026, 2, 19, 10, 0), datetime(2026, 2, 19, 11, 0)),
        location=Location(
            lat=lat,
            lon=lon,
            name=name,
            address=None,
            city=city,
            country=country,
        ),
        photos=[_photo(event_id)],
        sources=["exif"],
    )


def _trip_with_transit_noise() -> Trip:
    return Trip(
        name="New Zealand 2026",
        date_range=(date(2026, 2, 18), date(2026, 3, 6)),
        days=[
            Day(
                date=date(2026, 2, 19),
                events=[
                    _event(
                        "day01-event01",
                        "DFW to AKL",
                        event_type="transit",
                        city="Otu",
                        country="NG",
                        lat=6.69,
                        lon=4.90,
                    ),
                    _event(
                        "day02-event01",
                        "Auckland Central",
                        event_type="landmark",
                        city="Auckland",
                        country="NZ",
                        lat=-36.8485,
                        lon=174.7633,
                    ),
                ],
            )
        ],
    )


@pytest.mark.parametrize(
    "map_func",
    [
        "post_trip_summary.cli._generate_static_map",
        "post_trip_summary.server.app._generate_static_map",
    ],
)
def test_static_route_map_skips_transit_location_noise(tmp_path, monkeypatch, map_func):
    added_markers = []

    class FakeMarker:
        def __init__(self, coordinates, color, size):
            self.coordinates = coordinates

    class FakeImage:
        def save(self, path):
            Path(path).write_bytes(b"fake png")

    class FakeMap:
        def __init__(self, width, height):
            self.markers = []

        def add_marker(self, marker):
            self.markers.append(marker)
            added_markers.append(marker.coordinates)

        def render(self):
            return FakeImage()

    monkeypatch.setitem(
        sys.modules,
        "staticmap",
        SimpleNamespace(StaticMap=FakeMap, CircleMarker=FakeMarker),
    )
    module_name, attr_name = map_func.rsplit(".", 1)
    module = pytest.importorskip(module_name)

    assert getattr(module, attr_name)(_trip_with_transit_noise(), tmp_path) == "route-map.png"
    assert added_markers == [(174.7633, -36.8485)]
