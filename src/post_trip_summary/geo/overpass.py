"""Supplementary POI lookup — LocationIQ Nearby (primary) with Overpass fallback."""
import logging
import time

import requests

from post_trip_summary.geo.util import interruptible_sleep, locationiq_throttle

logger = logging.getLogger(__name__)

# Priority order for POI categories (lower index = higher priority)
_CATEGORY_PRIORITY = ["aeroway", "tourism", "historic", "amenity", "leisure"]

# Within tourism, destination types rank higher than support/info types
_TOURISM_HIGH = {"attraction", "museum", "gallery", "theme_park", "zoo", "aquarium", "artwork"}
_TOURISM_LOW = {"information", "viewpoint", "picnic_site", "camp_site", "caravan_site"}
_AEROWAY_HIGH = {"aerodrome"}
_AEROWAY_LOW = {"gate"}
_AIRPORT_AUGMENT_RADIUS_M = 1500

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _sort_key(r: dict) -> tuple:
    cat_rank = _CATEGORY_PRIORITY.index(r["category"]) if r["category"] in _CATEGORY_PRIORITY else 99
    if r["category"] == "aeroway":
        if r["type"] in _AEROWAY_HIGH:
            subtype_rank = 0
        elif r["type"] in _AEROWAY_LOW:
            subtype_rank = 2
        else:
            subtype_rank = 1
    elif r["category"] == "tourism":
        if r["type"] in _TOURISM_HIGH:
            subtype_rank = 0
        elif r["type"] in _TOURISM_LOW:
            subtype_rank = 2
        else:
            subtype_rank = 1
    else:
        subtype_rank = 1
    return (cat_rank, subtype_rank, r["distance_m"])


def pick_best_overpass_poi(pois: list[dict]) -> str:
    """Return the name of the highest-priority, closest POI, or empty string."""
    if not pois:
        return ""
    return pois[0]["name"]


# ---------------------------------------------------------------------------
# LocationIQ Nearby (primary)
# ---------------------------------------------------------------------------

_liq_api_key: str | None = None
_liq_exhausted = False
_liq_last_request = 0.0  # unused, kept for reset() compatibility
_LIQ_MIN_INTERVAL = 0.5  # unused, throttle is in util.py

# Map LocationIQ class names to our category system
_LIQ_CLASS_MAP = {
    "aeroway": "aeroway",
    "tourism": "tourism",
    "historic": "historic",
    "amenity": "amenity",
    "leisure": "leisure",
}


def _init_locationiq(api_key: str | None) -> None:
    global _liq_api_key
    _liq_api_key = api_key


def locationiq_poi_search(lat: float, lon: float, radius_m: int = 300) -> list[dict]:
    """Search for named POIs using LocationIQ Nearby API.

    Returns list of dicts with name, category, type, distance_m,
    sorted by category priority then distance.
    """
    global _liq_exhausted, _liq_last_request

    if not _liq_api_key or _liq_exhausted:
        return []

    locationiq_throttle()

    tag = "aeroway:aerodrome,aeroway:terminal,aeroway:gate,tourism:*,historic:*,amenity:restaurant,amenity:cafe,amenity:museum,amenity:gallery,amenity:theatre,amenity:library,amenity:place_of_worship,amenity:bar,amenity:pub,leisure:park,leisure:garden,leisure:nature_reserve,leisure:stadium"

    try:
        resp = requests.get(
            "https://us1.locationiq.com/v1/nearby",
            params={
                "key": _liq_api_key,
                "lat": lat,
                "lon": lon,
                "tag": tag,
                "radius": min(radius_m, 30000),
                "format": "json",
                "accept-language": "en",
                "limit": 10,
            },
            timeout=10,
        )

        if resp.status_code == 404:
            # No results found at this location (e.g., ocean) — not an error
            return []

        if resp.status_code == 429:
            logger.warning("LocationIQ Nearby rate limited, falling back to Overpass")
            return []

        if resp.status_code in (401, 403):
            logger.warning("LocationIQ Nearby auth error (%s), disabling for session", resp.status_code)
            _liq_exhausted = True
            return []

        resp.raise_for_status()
        data = resp.json()

    except requests.exceptions.Timeout:
        logger.debug("LocationIQ Nearby timed out for (%.4f, %.4f)", lat, lon)
        return []
    except Exception:
        logger.debug("LocationIQ Nearby failed for (%.4f, %.4f)", lat, lon, exc_info=True)
        return []

    if not isinstance(data, list):
        return []

    results = []
    for item in data:
        name = item.get("name")
        if not name:
            continue

        cls = item.get("class", "")
        type_val = item.get("type", "")
        category = _LIQ_CLASS_MAP.get(cls)
        if category is None:
            continue

        distance_m = float(item.get("distance", 0))

        results.append({
            "name": name,
            "category": category,
            "type": type_val,
            "distance_m": distance_m,
        })

    results.sort(key=_sort_key)
    return results


# ---------------------------------------------------------------------------
# Overpass API (fallback)
# ---------------------------------------------------------------------------

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Per-endpoint rate-limit tracking
_last_request_times: dict[str, float] = {}
_MIN_INTERVAL = 2.0  # seconds between requests to the same endpoint

# Circuit breaker: disable Overpass after consecutive failures
_consecutive_failures = 0
_FAILURE_THRESHOLD = 3  # disable after this many consecutive failures
_circuit_broken = False


def overpass_poi_search(lat: float, lon: float, radius_m: int = 300) -> list[dict]:
    """Search for named POIs near a coordinate using Overpass API.

    Returns list of dicts with name, category, type, distance_m,
    sorted by category priority then distance.
    """
    amenity_filter = (
        "restaurant|cafe|museum|gallery|theatre|library"
        "|place_of_worship|bar|pub"
    )
    leisure_filter = "park|garden|nature_reserve|stadium"
    aeroway_filter = "aerodrome|terminal|gate"

    query = f"""[out:json][timeout:10];
(
  node["aeroway"~"{aeroway_filter}"]["name"](around:{radius_m},{lat},{lon});
  way["aeroway"~"{aeroway_filter}"]["name"](around:{radius_m},{lat},{lon});
  relation["aeroway"~"{aeroway_filter}"]["name"](around:{radius_m},{lat},{lon});
  node["tourism"]["name"](around:{radius_m},{lat},{lon});
  way["tourism"]["name"](around:{radius_m},{lat},{lon});
  relation["tourism"]["name"](around:{radius_m},{lat},{lon});
  node["amenity"~"{amenity_filter}"]["name"](around:{radius_m},{lat},{lon});
  way["amenity"~"{amenity_filter}"]["name"](around:{radius_m},{lat},{lon});
  relation["amenity"~"{amenity_filter}"]["name"](around:{radius_m},{lat},{lon});
  node["historic"]["name"](around:{radius_m},{lat},{lon});
  way["historic"]["name"](around:{radius_m},{lat},{lon});
  relation["historic"]["name"](around:{radius_m},{lat},{lon});
  node["leisure"~"{leisure_filter}"]["name"](around:{radius_m},{lat},{lon});
  way["leisure"~"{leisure_filter}"]["name"](around:{radius_m},{lat},{lon});
  relation["leisure"~"{leisure_filter}"]["name"](around:{radius_m},{lat},{lon});
);
out center tags;"""

    global _consecutive_failures, _circuit_broken

    if _circuit_broken:
        return []

    try:
        elements = None
        for url in OVERPASS_ENDPOINTS:
            # Per-endpoint throttle
            last = _last_request_times.get(url, 0.0)
            elapsed = time.monotonic() - last
            if elapsed < _MIN_INTERVAL:
                interruptible_sleep(_MIN_INTERVAL - elapsed)

            try:
                _last_request_times[url] = time.monotonic()
                resp = requests.post(url, data={"data": query}, timeout=10)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 30))
                    logger.debug("Overpass 429 at %s, backing off %ds", url, retry_after)
                    _last_request_times[url] = time.monotonic() + retry_after
                    continue
                resp.raise_for_status()
                elements = resp.json().get("elements", [])
                _consecutive_failures = 0  # Reset on success
                break
            except requests.exceptions.HTTPError:
                logger.debug("Overpass endpoint %s failed, trying next", url)
                continue
            except requests.exceptions.Timeout:
                logger.debug("Overpass endpoint %s timed out, trying next", url)
                continue

        if elements is None:
            _consecutive_failures += 1
            if _consecutive_failures >= _FAILURE_THRESHOLD:
                _circuit_broken = True
                logger.warning(
                    "Overpass disabled for this session after %d consecutive failures",
                    _consecutive_failures,
                )
            else:
                logger.warning("All Overpass endpoints failed for (%.4f, %.4f)", lat, lon)
            return []
    except Exception:
        logger.warning("Overpass API request failed", exc_info=True)
        return []

    results = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        # Determine category and type
        category = None
        type_val = None
        for cat in _CATEGORY_PRIORITY:
            if cat in tags:
                category = cat
                type_val = tags[cat]
                break
        if category is None:
            continue

        # Element coordinates (ways/relations use center, nodes use direct lat/lon)
        if el.get("type") in ("way", "relation"):
            center = el.get("center", {})
            elat = center.get("lat", lat)
            elon = center.get("lon", lon)
        else:
            elat = el.get("lat", lat)
            elon = el.get("lon", lon)

        # Approximate distance in meters
        distance_m = ((lat - elat) ** 2 + (lon - elon) ** 2) ** 0.5 * 111_000

        results.append({
            "name": name,
            "category": category,
            "type": type_val,
            "distance_m": distance_m,
        })

    results.sort(key=_sort_key)
    return results


# ---------------------------------------------------------------------------
# Unified entry point: LocationIQ first, Overpass fallback
# ---------------------------------------------------------------------------

def poi_search(lat: float, lon: float, radius_m: int = 300) -> list[dict]:
    """Search for nearby POIs. Tries LocationIQ Nearby first, falls back to Overpass.

    Returns list of dicts with name, category, type, distance_m,
    sorted by category priority then distance.
    """
    results = locationiq_poi_search(lat, lon, radius_m=radius_m)
    if results:
        if _needs_airport_aerodrome_augmentation(results):
            augmented = results + overpass_poi_search(
                lat,
                lon,
                radius_m=max(radius_m, _AIRPORT_AUGMENT_RADIUS_M),
            )
            return _dedupe_and_sort_pois(augmented)
        return results

    return overpass_poi_search(lat, lon, radius_m=radius_m)


def _needs_airport_aerodrome_augmentation(results: list[dict]) -> bool:
    has_airport_terminal = any(
        result.get("category") == "aeroway"
        and result.get("type") in {"terminal", "gate"}
        for result in results
    )
    has_aerodrome = any(
        result.get("category") == "aeroway"
        and result.get("type") == "aerodrome"
        for result in results
    )
    return has_airport_terminal and not has_aerodrome


def _dedupe_and_sort_pois(results: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str, str], dict] = {}
    for result in results:
        key = (
            str(result.get("name", "")).casefold(),
            str(result.get("category", "")),
            str(result.get("type", "")),
        )
        existing = deduped.get(key)
        if existing is None or float(result.get("distance_m", 0.0)) < float(existing.get("distance_m", 0.0)):
            deduped[key] = result
    sorted_results = list(deduped.values())
    sorted_results.sort(key=_sort_key)
    return sorted_results
