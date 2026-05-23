"""Structured geolocation context for trip events."""
from __future__ import annotations

from collections.abc import Iterable

from geopy.distance import geodesic


GEO_POI_FIELDS = ("aeroway", "tourism", "amenity", "leisure", "historic", "shop", "natural")
AIRPORT_POI_TYPES = {"aerodrome"}
WALKING_CLUSTER_MIN_PHOTOS = 3
WALKING_CLUSTER_MIN_DURATION_MINUTES = 20.0
WALKING_CLUSTER_MIN_PATH_M = 500.0
WALKING_CLUSTER_MIN_RADIUS_M = 250.0
AIRPORT_TERMS = (
    "airport",
    "airfield",
    "aerodrome",
    "terminal",
    "gate",
)


def build_geo_context(geo: dict, cluster: dict | None = None) -> dict[str, object]:
    """Build compact, serializable location context from reverse geocode output."""
    nearby_pois = _clean_nearby_pois(geo.get("overpass_pois", []))
    poi_category, poi_type = _primary_poi_category(geo, nearby_pois)
    airport_name = _airport_name(nearby_pois, geo)
    cluster_metrics = _cluster_metrics(cluster)
    poi_name = str(geo.get("poi_name", "") or geo.get("overpass_poi_name", "") or "")
    area_name = str(geo.get("area_name", "") or geo.get("city", "") or "")
    place_name = str(geo.get("place_name", "") or poi_name or area_name)

    context = {
        "city": str(geo.get("city", "") or ""),
        "country": str(geo.get("country", "") or ""),
        "admin1": str(geo.get("admin1", "") or ""),
        "admin2": str(geo.get("admin2", "") or ""),
        "area_name": area_name,
        "place_name": place_name,
        "poi_name": poi_name,
        "poi_category": poi_category,
        "poi_type": poi_type,
        "airport_name": airport_name,
        "nearby_pois": nearby_pois,
        **cluster_metrics,
        "location_granularity": _location_granularity(poi_name, nearby_pois, area_name, geo),
    }
    context["is_airport"] = _contains_airport_signal(
        [
            context["place_name"],
            context["poi_name"],
            context["area_name"],
            context["poi_category"],
            context["poi_type"],
            context["airport_name"],
            *[poi["name"] for poi in nearby_pois],
        ]
    )
    return context


def _primary_poi_category(geo: dict, nearby_pois: list[dict[str, object]]) -> tuple[str, str]:
    for field in GEO_POI_FIELDS:
        value = str(geo.get(field, "") or "")
        if value:
            matching_nearby_type = _nearby_type_for_name(value, nearby_pois)
            return field, matching_nearby_type or value
    if nearby_pois:
        first = nearby_pois[0]
        return str(first.get("category", "")), str(first.get("type", ""))
    return "", ""


def _nearby_type_for_name(name: str, nearby_pois: list[dict[str, object]]) -> str:
    normalized = name.casefold()
    for poi in nearby_pois:
        if str(poi.get("name", "")).casefold() == normalized:
            return str(poi.get("type", "") or "")
    return ""


def _airport_name(nearby_pois: list[dict[str, object]], geo: dict) -> str:
    for poi in nearby_pois:
        if (
            str(poi.get("category", "")).lower() == "aeroway"
            and str(poi.get("type", "")).lower() in AIRPORT_POI_TYPES
        ):
            return str(poi.get("name", ""))
    direct_aeroway = str(geo.get("aeroway", "") or "")
    if _looks_like_airport_name(direct_aeroway):
        return direct_aeroway
    return ""


def _looks_like_airport_name(value: str) -> bool:
    normalized = value.lower()
    if not normalized:
        return False
    if any(term in normalized for term in ("terminal", "gate", "ticketing", "level")):
        return False
    return any(term in normalized for term in ("airport", "aerodrome", "airfield"))


def _location_granularity(
    poi_name: str,
    nearby_pois: list[dict[str, object]],
    area_name: str,
    geo: dict,
) -> str:
    if poi_name:
        return "poi"
    if nearby_pois:
        return "nearby_poi"
    if area_name:
        return "area"
    if geo.get("country"):
        return "country"
    return "unknown"


def _clean_nearby_pois(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []

    pois: list[dict[str, object]] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        pois.append(
            {
                "name": str(name),
                "category": str(item.get("category", "") or ""),
                "type": str(item.get("type", "") or ""),
                "distance_m": round(float(item.get("distance_m", 0.0)), 1),
            }
        )
    return pois


def _cluster_metrics(cluster: dict | None) -> dict[str, object]:
    metrics = {
        "gps_photo_count": 0,
        "gps_path_distance_m": 0.0,
        "gps_max_radius_m": 0.0,
        "duration_minutes": 0.0,
        "is_broad_walking_cluster": False,
    }
    if not cluster:
        return metrics

    photos = sorted(cluster.get("photos", []), key=lambda photo: photo.timestamp)
    gps_points = [photo.gps for photo in photos if getattr(photo, "gps", None)]
    metrics["gps_photo_count"] = len(gps_points)
    if cluster.get("time_range"):
        start, end = cluster["time_range"]
        metrics["duration_minutes"] = round((end - start).total_seconds() / 60, 1)
    if len(gps_points) >= 2:
        path_distance = sum(
            geodesic(start, end).meters
            for start, end in zip(gps_points, gps_points[1:])
        )
        metrics["gps_path_distance_m"] = round(path_distance, 1)
    centroid = cluster.get("centroid")
    if centroid and gps_points:
        metrics["gps_max_radius_m"] = round(
            max(geodesic(centroid, point).meters for point in gps_points),
            1,
        )
    metrics["is_broad_walking_cluster"] = (
        metrics["gps_photo_count"] >= WALKING_CLUSTER_MIN_PHOTOS
        and metrics["duration_minutes"] >= WALKING_CLUSTER_MIN_DURATION_MINUTES
        and (
            metrics["gps_path_distance_m"] >= WALKING_CLUSTER_MIN_PATH_M
            or metrics["gps_max_radius_m"] >= WALKING_CLUSTER_MIN_RADIUS_M
        )
    )
    return metrics


def _contains_airport_signal(values: Iterable[object]) -> bool:
    text = " ".join(str(value).lower() for value in values if value)
    return any(term in text for term in AIRPORT_TERMS)
