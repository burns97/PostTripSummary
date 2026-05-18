"""Metadata-only Vacation Blend Discovery scoring."""
from __future__ import annotations

from collections import defaultdict
from math import atan2, cos, radians, sin, sqrt
import re

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.taxonomy import VACATION_THEMES, get_theme_label
from post_trip_summary.models import Event, Trip

PRIMARY_THRESHOLD = 35.0
SECONDARY_THRESHOLD = 15.0

THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "road_trip": (
        "drive",
        "driving",
        "road",
        "highway",
        "scenic",
        "viewpoint",
        "overlook",
        "pass",
        "route",
        "lookout",
        "lake viewpoint",
    ),
    "adventure_outdoors": (
        "hike",
        "hiking",
        "trail",
        "walk",
        "kayak",
        "boat",
        "glacier",
        "alpine",
        "mountain",
        "cave",
        "adventure",
        "track",
    ),
    "nature_wildlife": (
        "park",
        "lake",
        "river",
        "forest",
        "waterfall",
        "wildlife",
        "garden",
        "zoo",
        "fjord",
        "volcano",
        "island",
        "mountain",
        "beach",
    ),
    "culture_sightseeing": (
        "museum",
        "gallery",
        "historic",
        "history",
        "temple",
        "church",
        "cathedral",
        "castle",
        "landmark",
        "monument",
        "village",
        "architecture",
        "art",
    ),
    "food_drink": (
        "restaurant",
        "cafe",
        "coffee",
        "bar",
        "market",
        "winery",
        "brewery",
        "tasting",
        "dinner",
        "lunch",
        "breakfast",
        "food",
        "menu",
    ),
    "beach_relaxation": (
        "beach",
        "pool",
        "sunset",
        "sunrise",
        "spa",
        "relax",
        "relaxation",
        "sand",
        "ocean",
        "sea",
    ),
    "nightlife_events": (
        "club",
        "casino",
        "show",
        "concert",
        "theater",
        "theatre",
        "bar",
        "lounge",
        "night",
        "party",
    ),
    "family_friends": (
        "friends",
        "family",
        "group",
        "party",
        "wedding",
        "reunion",
        "birthday",
        "anniversary",
        "ceremony",
        "graduation",
    ),
    "resort_luxury": (
        "resort",
        "hotel",
        "suite",
        "spa",
        "lounge",
        "fine dining",
        "tasting menu",
        "villa",
        "luxury",
    ),
    "shopping_city": (
        "shopping",
        "shop",
        "mall",
        "market",
        "boutique",
        "downtown",
        "city",
        "neighborhood",
        "district",
        "street",
    ),
    "wellness_slow": (
        "spa",
        "wellness",
        "yoga",
        "massage",
        "rest",
        "slow",
        "relax",
        "meditation",
        "retreat",
    ),
}

EVENT_TYPE_BOOSTS: dict[str, tuple[tuple[str, float, str], ...]] = {
    "restaurant": (("food_drink", 12.0, "restaurant events"),),
    "landmark": (("culture_sightseeing", 10.0, "landmark events"),),
    "hotel": (("resort_luxury", 10.0, "hotel events"),),
    "activity": (),
    "transit": (("road_trip", 8.0, "transit events"),),
    "unknown": (),
}


def discover_vacation_blend(trip: Trip) -> VacationBlend:
    """Infer a Vacation Blend from existing trip metadata without AI calls."""
    events = [event for day in trip.days for event in day.events]
    theme_scores = {theme.id: 0.0 for theme in VACATION_THEMES}
    evidence: dict[str, list[str]] = defaultdict(list)
    sample_event_ids: dict[str, list[str]] = defaultdict(list)

    for event in events:
        event_text = _event_text(event)
        for theme_id, keywords in THEME_KEYWORDS.items():
            matches = _matched_keywords(event_text, keywords)
            if not matches:
                continue
            score = min(24.0, len(matches) * 8.0)
            theme_scores[theme_id] += score
            _add_evidence(
                evidence[theme_id],
                f"{event.name} matched {', '.join(matches[:3])}",
            )
            _add_sample(sample_event_ids[theme_id], event.id)

        for theme_id, score, reason in EVENT_TYPE_BOOSTS.get(event.type, ()):
            theme_scores[theme_id] += score
            _add_evidence(evidence[theme_id], reason)
            _add_sample(sample_event_ids[theme_id], event.id)

        start_hour = event.time_range[0].hour
        if start_hour >= 20 or start_hour <= 4:
            theme_scores["nightlife_events"] += 8.0
            _add_evidence(evidence["nightlife_events"], "late evening event timing")
            _add_sample(sample_event_ids["nightlife_events"], event.id)

    movement = _movement_diagnostics(trip, events)
    movement_score = _road_trip_movement_score(movement)
    if movement_score:
        theme_scores["road_trip"] += movement_score
        _add_evidence(
            evidence["road_trip"],
            (
                f"movement across {movement['city_count']} cities, "
                f"{movement['day_count']} days, and {round(movement['gps_distance_km'])} km"
            ),
        )
        for event_id in movement["movement_event_ids"]:
            _add_sample(sample_event_ids["road_trip"], event_id)

    road_trip_eligible = _is_road_trip_eligible(movement)
    if not road_trip_eligible:
        theme_scores["road_trip"] = min(
            theme_scores["road_trip"],
            PRIMARY_THRESHOLD - 0.1,
        )

    clamped_scores = {
        theme_id: _clamp_score(score) for theme_id, score in theme_scores.items()
    }
    ranked = sorted(clamped_scores.items(), key=lambda item: (-item[1], item[0]))
    primary_ids = [
        theme_id for theme_id, score in ranked if score >= PRIMARY_THRESHOLD
    ][:3]
    secondary_ids = [
        theme_id
        for theme_id, score in ranked
        if theme_id not in primary_ids and score >= SECONDARY_THRESHOLD
    ][:5]

    primary = [
        _theme_score(theme_id, clamped_scores, evidence, sample_event_ids)
        for theme_id in primary_ids
    ]
    secondary = [
        _theme_score(theme_id, clamped_scores, evidence, sample_event_ids)
        for theme_id in secondary_ids
    ]

    top_score = ranked[0][1] if ranked else 0.0
    confidence = _confidence(primary, top_score)
    warnings = []
    if not primary or top_score < 20.0:
        warnings.append("metadata signal is weak; consider richer notes or photo analysis")

    diagnostics = {
        "event_count": len(events),
        "photo_count": sum(len(event.photos) for event in events),
        "city_count": movement["city_count"],
        "country_count": movement["country_count"],
        "day_count": movement["day_count"],
        "gps_distance_km": round(movement["gps_distance_km"], 1),
        "road_trip_eligible": road_trip_eligible,
        "theme_scores": clamped_scores,
    }

    return VacationBlend(
        analysis_mode="metadata_only",
        confidence=confidence,
        primary=primary,
        secondary=secondary,
        rejected=[],
        diagnostics=diagnostics,
        warnings=warnings,
    )


def _event_text(event: Event) -> str:
    location = event.location
    parts = [
        event.name,
        event.type,
        location.name,
        location.address or "",
        location.city,
        location.country,
        event.description,
        event.summary,
        event.notes,
    ]
    return " ".join(part for part in parts if part).lower()


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [
        keyword
        for keyword in keywords
        if re.search(rf"\b{re.escape(keyword)}\b", text)
    ]


def _movement_diagnostics(trip: Trip, events: list[Event]) -> dict[str, object]:
    cities = {event.location.city for event in events if event.location.city}
    countries = {event.location.country for event in events if event.location.country}
    event_points = [
        (event.id, event.location.lat, event.location.lon)
        for event in events
        if _has_real_coordinates(event.location.lat, event.location.lon)
    ]
    photo_points = [
        (photo.gps[0], photo.gps[1])
        for event in events
        for photo in event.photos
        if photo.gps and _has_real_coordinates(photo.gps[0], photo.gps[1])
    ]
    distance_points = [(lat, lon) for _, lat, lon in event_points] or photo_points
    gps_distance_km = _path_distance_km(distance_points)
    return {
        "city_count": len(cities),
        "country_count": len(countries),
        "day_count": len(trip.days),
        "gps_point_count": len(distance_points),
        "gps_distance_km": gps_distance_km,
        "movement_event_ids": [event_id for event_id, _, _ in event_points[:4]],
    }


def _road_trip_movement_score(movement: dict[str, object]) -> float:
    if not _is_road_trip_eligible(movement):
        return 0.0

    city_count = int(movement["city_count"])
    day_count = int(movement["day_count"])
    gps_distance_km = float(movement["gps_distance_km"])
    score = 18.0
    score += min(24.0, (city_count - 1) * 8.0)
    score += min(12.0, (day_count - 1) * 4.0)
    if gps_distance_km >= 100.0:
        score += 12.0
    elif gps_distance_km >= 50.0:
        score += 6.0
    return score


def _is_road_trip_eligible(movement: dict[str, object]) -> bool:
    city_count = int(movement["city_count"])
    day_count = int(movement["day_count"])
    gps_distance_km = float(movement["gps_distance_km"])
    return city_count >= 2 and day_count >= 2 and gps_distance_km >= 25.0


def _path_distance_km(points: list[tuple[float, float]]) -> float:
    return sum(
        _distance_km(start, end)
        for start, end in zip(points, points[1:])
    )


def _distance_km(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lon1 = start
    lat2, lon2 = end
    radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))


def _has_real_coordinates(lat: float, lon: float) -> bool:
    return bool(lat or lon)


def _theme_score(
    theme_id: str,
    scores: dict[str, float],
    evidence: dict[str, list[str]],
    sample_event_ids: dict[str, list[str]],
) -> ThemeScore:
    return ThemeScore(
        theme_id=theme_id,
        label=get_theme_label(theme_id),
        score=scores[theme_id],
        evidence=evidence.get(theme_id, [])[:4],
        sample_event_ids=sample_event_ids.get(theme_id, [])[:5],
    )


def _clamp_score(score: float) -> float:
    return round(max(0.0, min(100.0, score)), 1)


def _confidence(primary: list[ThemeScore], top_score: float) -> str:
    if not primary:
        return "low"
    if top_score >= 65.0:
        return "high"
    return "medium"


def _add_evidence(items: list[str], reason: str) -> None:
    if reason not in items:
        items.append(reason)


def _add_sample(items: list[str], event_id: str) -> None:
    if event_id not in items:
        items.append(event_id)
