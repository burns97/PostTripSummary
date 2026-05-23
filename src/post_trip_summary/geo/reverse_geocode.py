"""Reverse geocoding with persistent cache, LocationIQ, and Overpass POI enrichment."""
import logging
import time

from geopy.geocoders import Nominatim

from post_trip_summary.geo.util import interruptible_sleep, locationiq_throttle

from post_trip_summary.geo.cache import GeoCache
from post_trip_summary.geo.overpass import poi_search, pick_best_overpass_poi, _init_locationiq
from post_trip_summary.settings import get_geocoding_settings

logger = logging.getLogger(__name__)

GEO_SCHEMA_VERSION = 3

_EMPTY_RESULT = {
    "geo_schema_version": GEO_SCHEMA_VERSION,
    "city": "", "country": "", "admin1": "", "admin2": "",
    "suburb": "", "municipality": "", "tourism": "", "leisure": "",
    "natural": "", "state_district": "", "aeroway": "", "amenity": "", "shop": "",
    "historic": "", "road": "",
    "poi_name": "", "area_name": "", "place_name": "",
    "overpass_poi_name": "", "overpass_pois": [],
}

# Module-level state, lazy-initialized on first call
_nominatim = None
_locationiq = None
_locationiq_exhausted = False
_cache = None
_overpass_enabled = True
_overpass_radius_m = 300
_initialized = False

# Rate-limit tracking for Nominatim (LocationIQ uses shared throttle in util.py)
_nom_last_request = 0.0


def _build_geo_result(addr: dict) -> dict:
    """Extract geo fields from a Nominatim/LocationIQ address dict.

    Pure function — no network calls — so it's easy to unit-test.
    """
    city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("hamlet") or ""
    country = addr.get("country_code", "").upper()
    admin1 = addr.get("state", "")
    admin2 = addr.get("county", "")
    suburb = addr.get("suburb", "")
    municipality = addr.get("municipality", "")
    tourism = addr.get("tourism", "")
    aeroway = addr.get("aeroway", "")
    leisure = addr.get("leisure", "")
    natural = addr.get("natural", "")
    state_district = addr.get("state_district", "")
    amenity = addr.get("amenity", "")
    shop = addr.get("shop", "")
    historic = addr.get("historic", "")
    road = addr.get("road", "")

    # Specific POI name (most useful for event naming)
    poi_name = aeroway or tourism or amenity or leisure or historic or shop or natural or ""

    # Area/neighborhood name (useful for context)
    area_name = (
        city or suburb or municipality or state_district
        or admin2 or admin1 or ""
    )

    # Combined: prefer POI, fall back to area
    place_name = poi_name or area_name

    return {
        "city": city, "country": country, "admin1": admin1, "admin2": admin2,
        "suburb": suburb, "municipality": municipality, "tourism": tourism,
        "aeroway": aeroway,
        "leisure": leisure, "natural": natural, "state_district": state_district,
        "amenity": amenity, "shop": shop, "historic": historic, "road": road,
        "poi_name": poi_name, "area_name": area_name, "place_name": place_name,
        "overpass_poi_name": "", "overpass_pois": [],
        "geo_schema_version": GEO_SCHEMA_VERSION,
    }


def _init():
    """Lazy-initialize geocoders and cache from settings."""
    global _nominatim, _locationiq, _cache, _overpass_enabled, _overpass_radius_m, _initialized

    if _initialized:
        return

    settings = get_geocoding_settings()
    _nominatim = Nominatim(user_agent="post-trip-summary")

    api_key = settings.get("locationiq_api_key")
    if api_key:
        _locationiq = api_key  # Store API key; we call LocationIQ via requests
        _init_locationiq(api_key)  # Also enable LocationIQ Nearby POI search
        logger.info("LocationIQ geocoder configured (2 req/sec)")

    _overpass_enabled = settings.get("overpass_enabled", True)
    configured_radius = settings.get("overpass_radius_m", 300)
    _overpass_radius_m = max(configured_radius, 300)  # 300m minimum for large attractions
    _cache = GeoCache()
    _initialized = True


def _throttle_nominatim():
    """Wait if needed to respect Nominatim's 1 req/sec rate limit."""
    global _nom_last_request
    elapsed = time.monotonic() - _nom_last_request
    if elapsed < 1.0:
        interruptible_sleep(1.0 - elapsed)
    _nom_last_request = time.monotonic()


def _nominatim_reverse(lat: float, lon: float) -> dict:
    """Call Nominatim via geopy with 1 req/sec throttle."""
    _throttle_nominatim()
    location = _nominatim.reverse((lat, lon), language="en", exactly_one=True)
    if location is None:
        return dict(_EMPTY_RESULT)
    addr = location.raw.get("address", {})
    return _build_geo_result(addr)


def _locationiq_reverse(lat: float, lon: float) -> dict:
    """Call LocationIQ REST API with shared 2 req/sec throttle."""
    import requests

    locationiq_throttle()
    resp = requests.get(
        "https://us1.locationiq.com/v1/reverse",
        params={
            "key": _locationiq,
            "lat": lat,
            "lon": lon,
            "format": "json",
            "accept-language": "en",
            "addressdetails": 1,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    addr = data.get("address", {})
    return _build_geo_result(addr)


def _geocoder_lookup(lat: float, lon: float) -> dict:
    """Try LocationIQ first (if configured), fall back to Nominatim."""
    global _locationiq_exhausted
    import requests as _requests

    if _locationiq and not _locationiq_exhausted:
        try:
            return _locationiq_reverse(lat, lon)
        except _requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (401, 403, 429):
                # Auth or quota error — disable for session
                logger.warning("LocationIQ disabled (%s), falling back to Nominatim for remaining requests", exc)
                _locationiq_exhausted = True
            else:
                # Transient error (404 for ocean coords, 5xx, etc.) — fall back this request only
                logger.debug("LocationIQ error (%s), falling back to Nominatim for this request", exc)
        except Exception as exc:
            logger.debug("LocationIQ failed (%s), falling back to Nominatim for this request", exc)

    return _nominatim_reverse(lat, lon)


def reverse_geocode(lat: float, lon: float) -> dict:
    """Reverse geocode a coordinate with caching, LocationIQ, and Overpass enrichment."""
    _init()

    lat_r, lon_r = round(lat, 4), round(lon, 4)

    # 1. Check persistent disk cache
    cached = _cache.get(lat_r, lon_r)
    if cached is not None:
        if _overpass_enabled and cached.get("geo_schema_version") != GEO_SCHEMA_VERSION:
            _refresh_poi_candidates(lat_r, lon_r, cached)
            cached["geo_schema_version"] = GEO_SCHEMA_VERSION
            _cache_put(lat_r, lon_r, cached)
        return cached

    # 2. LocationIQ (if configured + not exhausted) -> Nominatim fallback
    result = _geocoder_lookup(lat_r, lon_r)

    # 3. POI lookup — LocationIQ Nearby (primary), Overpass (fallback)
    if _overpass_enabled:
        pois = poi_search(lat_r, lon_r, radius_m=_overpass_radius_m)
        result["overpass_poi_name"] = pick_best_overpass_poi(pois)
        result["overpass_pois"] = pois

    # 4. Cache and return
    result["geo_schema_version"] = GEO_SCHEMA_VERSION
    _cache_put(lat_r, lon_r, result)
    return result


def reverse_geocode_batch(coords: list[tuple[float, float]]) -> list[dict]:
    if not coords:
        return []
    return [reverse_geocode(lat, lon) for lat, lon in coords]


def _refresh_poi_candidates(lat: float, lon: float, result: dict) -> None:
    pois = poi_search(lat, lon, radius_m=_overpass_radius_m)
    result["overpass_poi_name"] = pick_best_overpass_poi(pois)
    result["overpass_pois"] = pois


def _cache_put(lat: float, lon: float, result: dict) -> None:
    try:
        _cache.put(lat, lon, result)
    except Exception:
        logger.debug("Failed to write geocode cache for (%.4f, %.4f)", lat, lon, exc_info=True)


def reset():
    """Reset module state. Useful for testing."""
    global _nominatim, _locationiq, _locationiq_exhausted, _cache
    global _overpass_enabled, _overpass_radius_m, _initialized
    global _nom_last_request
    _nominatim = None
    _locationiq = None
    _locationiq_exhausted = False
    _cache = None
    _overpass_enabled = True
    _overpass_radius_m = 300
    _initialized = False
    _nom_last_request = 0.0
