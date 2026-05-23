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
LONG_HAUL_SEGMENT_KM = 1000.0

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
        "cafe",
        "coffee",
        "bar",
        "market",
        "winery",
        "brewery",
        "tasting",
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
    "restaurant": (("food_drink", 9.0, "restaurant events"),),
    "activity": (),
    "transit": (),
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
            score = _keyword_score(theme_id, matches)
            theme_scores[theme_id] += score
            _add_evidence(
                evidence[theme_id],
                f"{event.name} matched {', '.join(matches[:3])}",
            )
            _add_sample(sample_event_ids[theme_id], event.id)

        for theme_id, score, reason in _event_type_boosts(event, event_text):
            theme_scores[theme_id] += score
            _add_evidence(evidence[theme_id], reason)
            _add_sample(sample_event_ids[theme_id], event.id)

        for theme_id, score, reason in _geo_context_boosts(event):
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
                f"destination movement across {movement['city_count']} cities, "
                f"{movement['day_count']} days, and "
                f"{round(movement['destination_movement_km'])} km"
            ),
        )
        if movement["long_haul_segment_count"]:
            _add_evidence(
                evidence["road_trip"],
                (
                    f"excluded {movement['long_haul_segment_count']} long-haul "
                    "flight-scale jumps from road-trip distance"
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
    coverage = _coverage_diagnostics(trip)
    if coverage["coverage_confidence"] == "low" and confidence == "high":
        confidence = "medium"
    if coverage["coverage_confidence"] == "low":
        warnings.append(
            (
                "partial trip sample detected: "
                f"{coverage['observed_days']} of {coverage['expected_days']} days have data"
            )
        )

    diagnostics = {
        "event_count": len(events),
        "photo_count": sum(len(event.photos) for event in events),
        "city_count": movement["city_count"],
        "country_count": movement["country_count"],
        "all_city_count": movement["all_city_count"],
        "all_country_count": movement["all_country_count"],
        "destination_city_count": movement["destination_city_count"],
        "destination_country_count": movement["destination_country_count"],
        "transit_city_count": movement["transit_city_count"],
        "destination_event_count": movement["destination_event_count"],
        "travel_logistics_event_count": movement["travel_logistics_event_count"],
        "day_count": movement["day_count"],
        "gps_distance_km": round(movement["gps_distance_km"], 1),
        "destination_movement_km": round(movement["destination_movement_km"], 1),
        "long_haul_transit_km": round(movement["long_haul_transit_km"], 1),
        "long_haul_segment_count": movement["long_haul_segment_count"],
        "road_trip_eligible": road_trip_eligible,
        "coverage": coverage,
        "geo_context": _geo_context_summary(events),
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
        location.name,
        location.city,
        location.country,
        event.description,
        event.summary,
        event.notes,
    ]
    return " ".join(part for part in parts if part).lower()


def _keyword_score(theme_id: str, matches: list[str]) -> float:
    if theme_id == "food_drink":
        return min(12.0, len(matches) * 6.0)
    if theme_id == "resort_luxury":
        return min(18.0, len(matches) * 8.0)
    return min(24.0, len(matches) * 8.0)


def _event_type_boosts(event: Event, event_text: str) -> tuple[tuple[str, float, str], ...]:
    if event.type != "landmark":
        return EVENT_TYPE_BOOSTS.get(event.type, ())

    nature_matches = _matched_keywords(
        event_text,
        THEME_KEYWORDS["nature_wildlife"]
        + THEME_KEYWORDS["adventure_outdoors"]
        + THEME_KEYWORDS["beach_relaxation"],
    )
    culture_matches = _matched_keywords(event_text, THEME_KEYWORDS["culture_sightseeing"])
    if nature_matches and not culture_matches:
        return (("nature_wildlife", 8.0, "natural landmark events"),)
    return (("culture_sightseeing", 10.0, "landmark events"),)


def _geo_context_boosts(event: Event) -> tuple[tuple[str, float, str], ...]:
    if _is_travel_logistics_event(event):
        return ()

    context = event.geo_context or {}
    if not context:
        return ()

    signals = [
        (
            str(context.get("poi_category", "") or "").lower(),
            str(context.get("poi_type", "") or "").lower(),
            str(context.get("place_name", "") or context.get("poi_name", "") or ""),
        )
    ]
    for poi in context.get("nearby_pois", []):
        if not isinstance(poi, dict):
            continue
        signals.append(
            (
                str(poi.get("category", "") or "").lower(),
                str(poi.get("type", "") or "").lower(),
                str(poi.get("name", "") or ""),
            )
        )

    best_by_theme: dict[str, tuple[float, str]] = {}
    for category, poi_type, name in signals:
        for theme_id, score in _theme_boosts_for_geo_signal(category, poi_type):
            reason = _geo_context_reason(category, poi_type, name)
            existing = best_by_theme.get(theme_id)
            if existing is None or score > existing[0]:
                best_by_theme[theme_id] = (score, reason)

    return tuple(
        (theme_id, score, reason)
        for theme_id, (score, reason) in best_by_theme.items()
    )


def _theme_boosts_for_geo_signal(
    category: str,
    poi_type: str,
) -> tuple[tuple[str, float], ...]:
    if category == "historic":
        return (("culture_sightseeing", 14.0),)
    if category == "natural":
        return (("nature_wildlife", 14.0),)
    if category == "shop":
        return (("shopping_city", 12.0),)

    if category == "amenity":
        if poi_type in {"restaurant", "cafe"}:
            return (("food_drink", 12.0),)
        if poi_type in {"bar", "pub"}:
            return (("food_drink", 8.0), ("nightlife_events", 8.0))
        if poi_type in {"museum", "gallery", "theatre", "library", "place_of_worship"}:
            return (("culture_sightseeing", 12.0),)

    if category == "leisure":
        if poi_type in {"park", "garden", "nature_reserve"}:
            return (("nature_wildlife", 12.0),)
        if poi_type == "stadium":
            return (("nightlife_events", 6.0),)

    if category == "tourism":
        if poi_type in {"museum", "gallery", "artwork", "theme_park", "attraction"}:
            return (("culture_sightseeing", 16.0),)
        if poi_type in {"viewpoint", "camp_site", "picnic_site"}:
            return (("nature_wildlife", 12.0), ("adventure_outdoors", 8.0))
        if poi_type in {"zoo", "aquarium"}:
            return (("nature_wildlife", 12.0),)
        return (("culture_sightseeing", 8.0),)

    return ()


def _geo_context_reason(category: str, poi_type: str, name: str) -> str:
    type_label = f"/{poi_type}" if poi_type else ""
    place = f" near {name}" if name else ""
    return f"geo context: {category}{type_label}{place}".strip()


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [
        keyword
        for keyword in keywords
        if re.search(rf"\b{re.escape(keyword)}\b", text)
    ]


def _movement_diagnostics(trip: Trip, events: list[Event]) -> dict[str, object]:
    destination_events = [event for event in events if not _is_travel_logistics_event(event)]
    travel_logistics_events = [
        event for event in events if _is_travel_logistics_event(event)
    ]
    all_cities = {event.location.city for event in events if event.location.city}
    all_countries = {event.location.country for event in events if event.location.country}
    destination_cities = {
        event.location.city for event in destination_events if event.location.city
    }
    destination_countries = {
        event.location.country for event in destination_events if event.location.country
    }
    transit_cities = {
        event.location.city for event in travel_logistics_events if event.location.city
    }
    event_points = sorted(
        [
            (
                event.id,
                event.time_range[0],
                event.location.lat,
                event.location.lon,
                _is_travel_logistics_event(event),
            )
            for event in events
            if _has_real_coordinates(event.location.lat, event.location.lon)
        ],
        key=lambda item: item[1],
    )
    photo_points = sorted(
        [
            (photo.timestamp, photo.gps[0], photo.gps[1])
            for event in events
            for photo in event.photos
            if photo.gps and _has_real_coordinates(photo.gps[0], photo.gps[1])
        ],
        key=lambda item: item[0],
    )
    distance_points = (
        [(event_id, lat, lon, is_logistics) for event_id, _, lat, lon, is_logistics in event_points]
        or [(None, lat, lon) for _, lat, lon in photo_points]
    )
    movement = _segmented_path_distance(distance_points)
    movement_event_ids = [
        event_id
        for event_id in movement["destination_event_ids"]
        if event_id is not None
    ][:4]
    if not movement_event_ids:
        movement_event_ids = [event_id for event_id, _, _, _, _ in event_points[:4]]
    return {
        "city_count": len(destination_cities),
        "country_count": len(destination_countries),
        "all_city_count": len(all_cities),
        "all_country_count": len(all_countries),
        "destination_city_count": len(destination_cities),
        "destination_country_count": len(destination_countries),
        "transit_city_count": len(transit_cities),
        "destination_event_count": len(destination_events),
        "travel_logistics_event_count": len(travel_logistics_events),
        "day_count": len(trip.days),
        "gps_point_count": len(distance_points),
        "gps_distance_km": movement["gps_distance_km"],
        "destination_movement_km": movement["destination_movement_km"],
        "long_haul_transit_km": movement["long_haul_transit_km"],
        "long_haul_segment_count": movement["long_haul_segment_count"],
        "movement_event_ids": movement_event_ids,
    }


def _segmented_path_distance(
    points: list[tuple]
) -> dict[str, object]:
    gps_distance_km = 0.0
    destination_movement_km = 0.0
    long_haul_transit_km = 0.0
    long_haul_segment_count = 0
    destination_event_ids: list[str | None] = []

    for start, end in zip(points, points[1:]):
        _, start_lat, start_lon, start_is_logistics = _distance_point(start)
        end_id, end_lat, end_lon, end_is_logistics = _distance_point(end)
        distance = _distance_km((start_lat, start_lon), (end_lat, end_lon))
        gps_distance_km += distance
        if distance >= LONG_HAUL_SEGMENT_KM:
            long_haul_transit_km += distance
            long_haul_segment_count += 1
            continue
        if start_is_logistics and end_is_logistics:
            continue
        destination_movement_km += distance
        destination_event_ids.append(end_id)

    return {
        "gps_distance_km": gps_distance_km,
        "destination_movement_km": destination_movement_km,
        "long_haul_transit_km": long_haul_transit_km,
        "long_haul_segment_count": long_haul_segment_count,
        "destination_event_ids": destination_event_ids,
    }


def _distance_point(point: tuple) -> tuple[str | None, float, float, bool]:
    if len(point) == 3:
        event_id, lat, lon = point
        return event_id, lat, lon, False
    event_id, lat, lon, is_logistics = point
    return event_id, lat, lon, bool(is_logistics)


def _geo_context_summary(events: list[Event]) -> dict[str, object]:
    granularity_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
    type_counts: dict[str, int] = defaultdict(int)
    events_with_geo_context = 0
    airport_event_count = 0

    for event in events:
        context = event.geo_context or {}
        if not context:
            continue
        events_with_geo_context += 1
        if context.get("is_airport") is True:
            airport_event_count += 1
        _count_context_value(granularity_counts, context.get("location_granularity"))
        event_categories = _event_context_values(context, "poi_category", "category")
        event_types = _event_context_values(context, "poi_type", "type")
        for category in event_categories:
            category_counts[category] += 1
        for poi_type in event_types:
            type_counts[poi_type] += 1

    return {
        "events_with_geo_context": events_with_geo_context,
        "airport_event_count": airport_event_count,
        "location_granularity_counts": dict(sorted(granularity_counts.items())),
        "poi_category_counts": dict(sorted(category_counts.items())),
        "poi_type_counts": dict(sorted(type_counts.items())),
    }


def _event_context_values(
    context: dict[str, object],
    primary_key: str,
    nearby_key: str,
) -> set[str]:
    values = {str(context[primary_key])} if context.get(primary_key) else set()
    for poi in context.get("nearby_pois", []):
        if not isinstance(poi, dict):
            continue
        value = poi.get(nearby_key)
        if value:
            values.add(str(value))
    return values


def _count_context_value(counts: dict[str, int], value: object) -> None:
    if value:
        counts[str(value)] += 1


def _is_travel_logistics_event(event: Event) -> bool:
    if event.geo_context.get("is_airport") is True:
        return True
    text = " ".join(
        str(part).lower()
        for part in [
            event.type,
            event.name,
            event.location.name,
            event.description,
            event.summary,
            event.notes,
        ]
        if part
    )
    logistics_terms = (
        "airport",
        "layover",
        "departure",
        "arrival",
        "terminal",
        "gate",
        "flight",
    )
    if event.type == "transit" and any(term in text for term in logistics_terms):
        return True
    return any(term in text for term in ("airport", "layover", "terminal", "gate"))


def _coverage_diagnostics(trip: Trip) -> dict[str, object]:
    expected_days = max(1, (trip.date_range[1] - trip.date_range[0]).days + 1)
    observed_days = len([day for day in trip.days if day.events])
    ratio = observed_days / expected_days
    if ratio < 0.5:
        coverage_confidence = "low"
    elif ratio < 0.85:
        coverage_confidence = "medium"
    else:
        coverage_confidence = "high"
    return {
        "expected_days": expected_days,
        "observed_days": observed_days,
        "coverage_ratio": round(ratio, 2),
        "coverage_confidence": coverage_confidence,
    }


def _road_trip_movement_score(movement: dict[str, object]) -> float:
    if not _is_road_trip_eligible(movement):
        return 0.0

    city_count = int(movement["city_count"])
    day_count = int(movement["day_count"])
    gps_distance_km = float(movement["destination_movement_km"])
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
    gps_distance_km = float(movement["destination_movement_km"])
    return city_count >= 2 and day_count >= 2 and gps_distance_km >= 25.0


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
