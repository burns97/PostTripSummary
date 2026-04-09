"""Tests for the persistent SQLite geocache."""

import pytest

from post_trip_summary.geo.cache import GeoCache

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _sample_result() -> dict:
    """A realistic geocode result dict."""
    return {
        "name": "Eiffel Tower",
        "address": {
            "tourism": "Eiffel Tower",
            "road": "Avenue Anatole France",
            "city": "Paris",
            "country": "France",
        },
        "lat": 48.8584,
        "lon": 2.2945,
        "type": "tourism",
    }


def _make_cache(tmp_path) -> GeoCache:
    """Create a GeoCache using a temporary directory."""
    return GeoCache(db_path=tmp_path / "geocache.db")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_get_missing_returns_none(tmp_path):
    cache = _make_cache(tmp_path)
    assert cache.get(48.8584, 2.2945) is None


def test_put_then_get_roundtrip(tmp_path):
    cache = _make_cache(tmp_path)
    result = _sample_result()
    cache.put(48.8584, 2.2945, result)
    assert cache.get(48.8584, 2.2945) == result


def test_overwrite_returns_latest(tmp_path):
    cache = _make_cache(tmp_path)
    cache.put(48.8584, 2.2945, {"name": "Old"})
    cache.put(48.8584, 2.2945, {"name": "New"})
    assert cache.get(48.8584, 2.2945) == {"name": "New"}


def test_clear_empties_cache(tmp_path):
    cache = _make_cache(tmp_path)
    cache.put(48.8584, 2.2945, _sample_result())
    cache.put(40.6892, -74.0445, {"name": "Statue of Liberty"})
    assert len(cache) == 2
    cache.clear()
    assert len(cache) == 0
    assert cache.get(48.8584, 2.2945) is None


def test_len(tmp_path):
    cache = _make_cache(tmp_path)
    assert len(cache) == 0
    cache.put(48.8584, 2.2945, _sample_result())
    assert len(cache) == 1
    cache.put(40.6892, -74.0445, {"name": "Statue of Liberty"})
    assert len(cache) == 2
