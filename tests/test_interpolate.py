# tests/test_interpolate.py
from datetime import datetime
from pathlib import Path

from post_trip_summary.models import Photo
from post_trip_summary.geo.interpolate import interpolate_missing_gps


def _photo(ts_str: str, gps=None) -> Photo:
    return Photo(path=Path("test.jpg"), timestamp=datetime.fromisoformat(ts_str), gps=gps)


def test_interpolate_midpoint():
    photos = [
        _photo("2025-01-01T10:00:00", gps=(-36.0, 174.0)),
        _photo("2025-01-01T11:00:00"),  # missing
        _photo("2025-01-01T12:00:00", gps=(-37.0, 175.0)),
    ]
    interpolate_missing_gps(photos)
    assert photos[1].gps is not None
    lat, lon = photos[1].gps
    assert abs(lat - (-36.5)) < 0.01
    assert abs(lon - 174.5) < 0.01


def test_interpolate_start_edge():
    photos = [
        _photo("2025-01-01T10:00:00"),  # missing, first
        _photo("2025-01-01T11:00:00", gps=(-36.0, 174.0)),
    ]
    interpolate_missing_gps(photos)
    assert photos[0].gps == (-36.0, 174.0)


def test_interpolate_end_edge():
    photos = [
        _photo("2025-01-01T10:00:00", gps=(-36.0, 174.0)),
        _photo("2025-01-01T11:00:00"),  # missing, last
    ]
    interpolate_missing_gps(photos)
    assert photos[1].gps == (-36.0, 174.0)


def test_interpolate_all_missing():
    photos = [
        _photo("2025-01-01T10:00:00"),
        _photo("2025-01-01T11:00:00"),
    ]
    interpolate_missing_gps(photos)
    assert photos[0].gps is None
    assert photos[1].gps is None


def test_interpolate_max_gap_exceeded():
    photos = [
        _photo("2025-01-01T08:00:00", gps=(-36.0, 174.0)),
        _photo("2025-01-01T14:00:00"),  # 6 hours later, exceeds 4hr cap
        _photo("2025-01-01T20:00:00", gps=(-37.0, 175.0)),
    ]
    interpolate_missing_gps(photos)
    # Should NOT interpolate — gap exceeds 4 hours
    assert photos[1].gps is None


def test_interpolate_all_have_gps():
    photos = [
        _photo("2025-01-01T10:00:00", gps=(-36.0, 174.0)),
        _photo("2025-01-01T11:00:00", gps=(-37.0, 175.0)),
    ]
    interpolate_missing_gps(photos)
    assert photos[0].gps == (-36.0, 174.0)
    assert photos[1].gps == (-37.0, 175.0)


def test_interpolate_empty_list():
    interpolate_missing_gps([])
