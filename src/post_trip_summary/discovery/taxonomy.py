"""Controlled Vacation Blend theme taxonomy."""
from __future__ import annotations

from post_trip_summary.discovery.models import ThemeDefinition

VACATION_THEMES: tuple[ThemeDefinition, ...] = (
    ThemeDefinition(id="road_trip", label="Road trip", description="Frequent movement, scenic drives, many stops, changing locations"),
    ThemeDefinition(id="adventure_outdoors", label="Adventure & outdoors", description="Hiking, boats, viewpoints, rugged terrain, active outdoor travel"),
    ThemeDefinition(id="culture_sightseeing", label="Culture & sightseeing", description="Museums, architecture, historic sites, landmarks, neighborhoods"),
    ThemeDefinition(id="food_drink", label="Food & drink", description="Restaurants, markets, cafes, wineries, breweries, cooking"),
    ThemeDefinition(id="beach_relaxation", label="Beach & relaxation", description="Beach, pool, sun, slow days, resort downtime"),
    ThemeDefinition(id="nightlife_events", label="Nightlife & events", description="Clubs, casinos, concerts, shows, evening venues, parties"),
    ThemeDefinition(id="family_friends", label="Family & friends", description="Family, friends, group photos, social moments, portraits"),
    ThemeDefinition(id="resort_luxury", label="Resort & luxury", description="Hotels, suites, spas, amenities, fine dining, premium experiences"),
    ThemeDefinition(id="shopping_city", label="Shopping & city life", description="Shopping, markets, neighborhoods, urban exploring, city landmarks"),
    ThemeDefinition(id="wellness_slow", label="Wellness & slow travel", description="Spas, rest days, wellness activities, slow mornings, reflective travel"),
    ThemeDefinition(id="nature_wildlife", label="Nature & wildlife", description="Landscapes, animals, parks, gardens, natural features"),
)

_THEME_BY_ID = {theme.id: theme for theme in VACATION_THEMES}


def get_theme_label(theme_id: str) -> str:
    return _THEME_BY_ID[theme_id].label


def validate_theme_ids(theme_ids: list[str]) -> None:
    unknown = sorted({theme_id for theme_id in theme_ids if theme_id not in _THEME_BY_ID})
    if unknown:
        raise ValueError(f"unknown theme id: {', '.join(unknown)}")
