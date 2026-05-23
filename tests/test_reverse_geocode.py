# tests/test_reverse_geocode.py
from post_trip_summary.geo import reverse_geocode as reverse_geocode_module
from post_trip_summary.geo.reverse_geocode import reverse_geocode, reverse_geocode_batch, _build_geo_result


def test_reverse_geocode_paris():
    result = reverse_geocode(48.8584, 2.2945)
    assert result is not None
    assert result["country"] == "FR"
    assert len(result["city"]) > 0


def test_reverse_geocode_batch_multiple():
    coords = [(48.8584, 2.2945), (40.7128, -74.0060)]
    results = reverse_geocode_batch(coords)
    assert len(results) == 2
    countries = {r["country"] for r in results}
    assert "FR" in countries


def test_reverse_geocode_invalid():
    result = reverse_geocode(0.0, 0.0)
    assert result is not None


def test_cached_result_without_current_schema_refreshes_poi_candidates(monkeypatch):
    class FakeCache:
        def __init__(self):
            self.value = {
                "city": "Columbus",
                "country": "US",
                "poi_name": "Brewdog",
                "area_name": "Columbus",
                "place_name": "Columbus",
                "overpass_poi_name": "Brewdog",
                "overpass_pois": [
                    {"name": "Brewdog", "category": "amenity", "type": "bar", "distance_m": 14.0}
                ],
            }
            self.saved = None

        def get(self, lat, lon):
            return dict(self.value)

        def put(self, lat, lon, result):
            self.saved = result

    fake_cache = FakeCache()
    airport_pois = [
        {
            "name": "John Glenn Columbus International Airport",
            "category": "aeroway",
            "type": "aerodrome",
            "distance_m": 140.0,
        },
        {"name": "Brewdog", "category": "amenity", "type": "bar", "distance_m": 14.0},
    ]

    monkeypatch.setattr(reverse_geocode_module, "_initialized", True)
    monkeypatch.setattr(reverse_geocode_module, "_cache", fake_cache)
    monkeypatch.setattr(reverse_geocode_module, "_overpass_enabled", True)
    monkeypatch.setattr(reverse_geocode_module, "_overpass_radius_m", 300)
    monkeypatch.setattr(reverse_geocode_module, "poi_search", lambda lat, lon, radius_m: airport_pois)

    result = reverse_geocode_module.reverse_geocode(39.9978639, -82.8824528)

    assert result["geo_schema_version"] == reverse_geocode_module.GEO_SCHEMA_VERSION
    assert result["overpass_poi_name"] == "John Glenn Columbus International Airport"
    assert fake_cache.saved == result


# --- _build_geo_result unit tests (no network calls) ---

def test_build_geo_result_city_present():
    addr = {"city": "Auckland", "state": "Auckland Region", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["city"] == "Auckland"
    assert result["poi_name"] == ""
    assert result["area_name"] == "Auckland"
    assert result["place_name"] == "Auckland"
    assert result["country"] == "NZ"


def test_build_geo_result_rural_fallback():
    addr = {"county": "Waikato District", "state": "Waikato", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["city"] == ""
    assert result["place_name"] == "Waikato District"
    assert result["admin1"] == "Waikato"


def test_build_geo_result_tourism():
    addr = {"tourism": "Hobbiton Movie Set", "state": "Waikato", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["tourism"] == "Hobbiton Movie Set"
    assert result["poi_name"] == "Hobbiton Movie Set"
    assert result["place_name"] == "Hobbiton Movie Set"


def test_build_geo_result_natural():
    addr = {"natural": "Lake Taupo", "state": "Waikato", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["natural"] == "Lake Taupo"
    assert result["place_name"] == "Lake Taupo"


def test_build_geo_result_suburb_fallback():
    addr = {"suburb": "Ponsonby", "city": "", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["place_name"] == "Ponsonby"


def test_build_geo_result_poi_over_city():
    """When both city and a POI field exist, poi_name wins for place_name."""
    addr = {"city": "Hamilton", "tourism": "Hamilton Gardens", "state": "Waikato", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["poi_name"] == "Hamilton Gardens"
    assert result["area_name"] == "Hamilton"
    assert result["place_name"] == "Hamilton Gardens"


def test_build_geo_result_amenity():
    addr = {"amenity": "Auckland Airport", "city": "Auckland", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["poi_name"] == "Auckland Airport"
    assert result["amenity"] == "Auckland Airport"
    assert result["area_name"] == "Auckland"


def test_build_geo_result_shop():
    addr = {"shop": "Countdown", "suburb": "Ponsonby", "city": "Auckland", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["poi_name"] == "Countdown"
    assert result["shop"] == "Countdown"


def test_build_geo_result_empty():
    result = _build_geo_result({})
    assert result["city"] == ""
    assert result["country"] == ""
    assert result["place_name"] == ""
    assert result["poi_name"] == ""
    assert result["area_name"] == ""
    assert result["tourism"] == ""
    assert result["natural"] == ""
