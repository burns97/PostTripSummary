# tests/test_reverse_geocode.py
from post_trip_summary.geo.reverse_geocode import reverse_geocode, reverse_geocode_batch


def test_reverse_geocode_paris():
    result = reverse_geocode(48.8584, 2.2945)
    assert result is not None
    # reverse_geocoder returns ISO country codes (e.g. "FR"), not full names
    assert result["country"] == "France" or result["country"] == "FR"
    assert len(result["city"]) > 0


def test_reverse_geocode_batch_multiple():
    coords = [(48.8584, 2.2945), (40.7128, -74.0060)]
    results = reverse_geocode_batch(coords)
    assert len(results) == 2
    countries = {r["country"] for r in results}
    assert "France" in countries or "FR" in countries


def test_reverse_geocode_invalid():
    result = reverse_geocode(0.0, 0.0)
    assert result is not None
