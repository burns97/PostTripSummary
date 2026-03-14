"""Reverse geocoding using geopy's Nominatim with local caching."""
import time
from functools import lru_cache

from geopy.geocoders import Nominatim

_geocoder = Nominatim(user_agent="post-trip-summary")

# Rate-limit tracking for Nominatim's 1 req/sec policy
_last_request_time = 0.0


_EMPTY_RESULT = {
    "city": "", "country": "", "admin1": "", "admin2": "",
    "suburb": "", "municipality": "", "tourism": "", "leisure": "",
    "natural": "", "state_district": "", "place_name": "",
}


def _build_geo_result(addr: dict) -> dict:
    """Extract geo fields from a Nominatim address dict.

    Pure function — no network calls — so it's easy to unit-test.
    """
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or ""
    country = addr.get("country_code", "").upper()
    admin1 = addr.get("state", "")
    admin2 = addr.get("county", "")
    suburb = addr.get("suburb", "")
    municipality = addr.get("municipality", "")
    tourism = addr.get("tourism", "")
    leisure = addr.get("leisure", "")
    natural = addr.get("natural", "")
    state_district = addr.get("state_district", "")

    # Best human-readable name via priority chain
    place_name = (
        city or tourism or leisure or natural
        or suburb or municipality or state_district
        or admin2 or admin1
    )

    return {
        "city": city, "country": country, "admin1": admin1, "admin2": admin2,
        "suburb": suburb, "municipality": municipality, "tourism": tourism,
        "leisure": leisure, "natural": natural, "state_district": state_district,
        "place_name": place_name,
    }


def _throttled_reverse(lat: float, lon: float):
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_request_time = time.monotonic()
    return _geocoder.reverse((lat, lon), language="en", exactly_one=True)


@lru_cache(maxsize=4096)
def _cached_reverse(lat_rounded: float, lon_rounded: float) -> dict:
    """Cache by rounded coords so nearby points reuse results."""
    location = _throttled_reverse(lat_rounded, lon_rounded)
    if location is None:
        return dict(_EMPTY_RESULT)
    addr = location.raw.get("address", {})
    return _build_geo_result(addr)


def reverse_geocode(lat: float, lon: float) -> dict:
    # Round to ~1.1km precision to maximize cache hits
    return _cached_reverse(round(lat, 2), round(lon, 2))


def reverse_geocode_batch(coords: list[tuple[float, float]]) -> list[dict]:
    if not coords:
        return []
    return [reverse_geocode(lat, lon) for lat, lon in coords]
