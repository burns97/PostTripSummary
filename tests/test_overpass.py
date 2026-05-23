"""Tests for geo.overpass — Overpass API POI lookup."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from post_trip_summary.geo.overpass import (
    overpass_poi_search,
    pick_best_overpass_poi,
    poi_search,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _poi(name: str, category: str, type_val: str, distance_m: float) -> dict:
    return {"name": name, "category": category, "type": type_val, "distance_m": distance_m}


def _overpass_element(
    name: str,
    category: str,
    type_val: str,
    lat: float,
    lon: float,
    *,
    el_type: str = "node",
) -> dict:
    """Build a fake Overpass JSON element."""
    tags = {"name": name, category: type_val}
    el = {"type": el_type, "tags": tags}
    if el_type == "way":
        el["center"] = {"lat": lat, "lon": lon}
    else:
        el["lat"] = lat
        el["lon"] = lon
    return el


# ---------------------------------------------------------------------------
# Unit tests — pick_best_overpass_poi
# ---------------------------------------------------------------------------

class TestPickBestOverpassPoi:
    def test_empty_list_returns_empty_string(self):
        assert pick_best_overpass_poi([]) == ""

    def test_single_poi_returns_name(self):
        assert pick_best_overpass_poi([_poi("Louvre", "tourism", "museum", 10.0)]) == "Louvre"

    def test_tourism_beats_amenity_regardless_of_distance(self):
        pois = [
            _poi("Far Museum", "tourism", "museum", 70.0),
            _poi("Close Cafe", "amenity", "cafe", 5.0),
        ]
        # List is pre-sorted by caller (overpass_poi_search)
        assert pick_best_overpass_poi(pois) == "Far Museum"

    def test_within_same_category_closer_wins(self):
        pois = [
            _poi("Near Church", "amenity", "place_of_worship", 10.0),
            _poi("Far Pub", "amenity", "pub", 60.0),
        ]
        assert pick_best_overpass_poi(pois) == "Near Church"

    def test_historic_beats_amenity_but_loses_to_tourism(self):
        pois = [
            _poi("Palace", "tourism", "attraction", 50.0),
            _poi("Old Wall", "historic", "ruins", 20.0),
            _poi("Bistro", "amenity", "restaurant", 5.0),
        ]
        assert pick_best_overpass_poi(pois) == "Palace"


# ---------------------------------------------------------------------------
# Unit test — overpass_poi_search sorting (mocked network)
# ---------------------------------------------------------------------------

class TestOverpassPoiSearchSorting:
    @patch("post_trip_summary.geo.overpass.requests.post")
    @patch("post_trip_summary.geo.overpass._last_request_times", {})
    def test_results_sorted_by_category_then_distance(self, mock_post):
        base_lat, base_lon = 48.8584, 2.2945

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                _overpass_element("Cafe Nearby", "amenity", "cafe", base_lat + 0.0001, base_lon),
                _overpass_element("Monument", "historic", "monument", base_lat + 0.0003, base_lon),
                _overpass_element("Museum", "tourism", "museum", base_lat + 0.0005, base_lon),
                _overpass_element("Park", "leisure", "park", base_lat + 0.0002, base_lon, el_type="way"),
            ],
        }
        mock_post.return_value = mock_response

        results = overpass_poi_search(base_lat, base_lon, radius_m=100)

        assert len(results) == 4

        # Verify ordering: tourism > historic > amenity > leisure
        assert results[0]["name"] == "Museum"
        assert results[0]["category"] == "tourism"
        assert results[1]["name"] == "Monument"
        assert results[1]["category"] == "historic"
        assert results[2]["name"] == "Cafe Nearby"
        assert results[2]["category"] == "amenity"
        assert results[3]["name"] == "Park"
        assert results[3]["category"] == "leisure"

        # Verify expected fields present
        for r in results:
            assert "name" in r
            assert "category" in r
            assert "type" in r
            assert "distance_m" in r
            assert isinstance(r["distance_m"], float)

    @patch("post_trip_summary.geo.overpass.requests.post")
    @patch("post_trip_summary.geo.overpass._last_request_times", {})
    def test_airport_aeroway_beats_terminal_amenities(self, mock_post):
        base_lat, base_lon = 39.9979, -82.8825

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                _overpass_element("Brewdog", "amenity", "bar", base_lat + 0.0001, base_lon),
                _overpass_element(
                    "John Glenn Columbus International Airport",
                    "aeroway",
                    "aerodrome",
                    base_lat + 0.001,
                    base_lon,
                    el_type="way",
                ),
                _overpass_element("Starbucks", "amenity", "cafe", base_lat + 0.0002, base_lon),
            ],
        }
        mock_post.return_value = mock_response

        results = overpass_poi_search(base_lat, base_lon, radius_m=500)

        assert results[0]["name"] == "John Glenn Columbus International Airport"
        assert results[0]["category"] == "aeroway"
        assert results[0]["type"] == "aerodrome"
        assert [result["name"] for result in results[1:]] == ["Brewdog", "Starbucks"]

    @patch("post_trip_summary.geo.overpass.requests.post")
    @patch("post_trip_summary.geo.overpass._last_request_times", {})
    def test_elements_without_name_are_skipped(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "elements": [
                {"type": "node", "lat": 48.0, "lon": 2.0, "tags": {"tourism": "viewpoint"}},
                _overpass_element("Named Place", "tourism", "museum", 48.0, 2.0),
            ],
        }
        mock_post.return_value = mock_response

        results = overpass_poi_search(48.0, 2.0)
        assert len(results) == 1
        assert results[0]["name"] == "Named Place"

    @patch("post_trip_summary.geo.overpass.requests.post")
    @patch("post_trip_summary.geo.overpass._last_request_times", {})
    def test_request_failure_returns_empty_list(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("timed out")

        results = overpass_poi_search(48.0, 2.0)
        assert results == []

    @patch("post_trip_summary.geo.overpass.overpass_poi_search")
    @patch("post_trip_summary.geo.overpass.locationiq_poi_search")
    def test_terminal_only_locationiq_results_are_augmented_with_airport_aerodrome(
        self,
        mock_locationiq,
        mock_overpass,
    ):
        mock_locationiq.return_value = [
            _poi("Ticketing Level", "aeroway", "terminal", 73.0),
            _poi("Brewdog", "amenity", "bar", 14.0),
        ]
        mock_overpass.return_value = [
            _poi("John Glenn Columbus International Airport", "aeroway", "aerodrome", 450.0),
        ]

        results = poi_search(39.9979, -82.8825, radius_m=300)

        assert results[0]["name"] == "John Glenn Columbus International Airport"
        assert results[0]["type"] == "aerodrome"
        assert "Ticketing Level" in [result["name"] for result in results]
        mock_overpass.assert_called_once_with(39.9979, -82.8825, radius_m=1500)


# ---------------------------------------------------------------------------
# Integration test — hits real Overpass API
# ---------------------------------------------------------------------------

class TestOverpassIntegration:
    @pytest.mark.integration
    def test_eiffel_tower_returns_tourism_poi(self):
        # Hits real Overpass API — requires network access
        results = overpass_poi_search(48.8584, 2.2945, radius_m=100)
        if not results:
            pytest.skip("Overpass API unavailable (all endpoints failed)")
        categories = {r["category"] for r in results}
        assert "tourism" in categories
