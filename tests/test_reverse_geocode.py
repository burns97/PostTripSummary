# tests/test_reverse_geocode.py
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


# --- _build_geo_result unit tests (no network calls) ---

def test_build_geo_result_city_present():
    addr = {"city": "Auckland", "state": "Auckland Region", "country_code": "nz"}
    result = _build_geo_result(addr)
    assert result["city"] == "Auckland"
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


def test_build_geo_result_empty():
    result = _build_geo_result({})
    assert result["city"] == ""
    assert result["country"] == ""
    assert result["place_name"] == ""
    assert result["tourism"] == ""
    assert result["natural"] == ""
