# tests/test_triage.py
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from post_trip_summary.models import Photo, Event, Location
from post_trip_summary.vision.triage import select_representatives, is_confidently_identified, estimate_batch_cost


def _photo(name: str, lat: float = 48.858, lon: float = 2.294) -> Photo:
    return Photo(path=Path(f"/photos/{name}.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(lat, lon))


def _event(name: str, sources: list[str], photos: list[Photo] | None = None) -> Event:
    return Event(
        id="day01-event01", type="landmark", name=name,
        time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
        location=Location(lat=48.858, lon=2.294, name=name, address=None, city="Paris", country="France"),
        photos=photos or [_photo(f"img{i}") for i in range(10)],
        description="", notes="", sources=sources,
    )


def test_confidently_identified_two_sources():
    event = _event("Eiffel Tower", sources=["exif", "itinerary"])
    assert is_confidently_identified(event) is True


def test_not_confidently_identified_one_source():
    event = _event("Unknown", sources=["exif"])
    assert is_confidently_identified(event) is False


def test_select_representatives_limits_count():
    photos = [_photo(f"img{i}") for i in range(50)]
    selected = select_representatives(photos, max_count=5)
    assert len(selected) <= 5


def test_select_representatives_returns_photos():
    photos = [_photo(f"img{i}") for i in range(3)]
    selected = select_representatives(photos, max_count=5)
    assert len(selected) == 3  # All 3 when under limit


def test_estimate_batch_cost():
    """With no provider, cost is 0. With a provider, delegates to it."""
    assert estimate_batch_cost(num_images=100) == 0.0

    from unittest.mock import MagicMock
    mock_provider = MagicMock()
    mock_provider.estimate_cost.return_value = 1.5
    assert estimate_batch_cost(num_images=100, provider=mock_provider) == 1.5
