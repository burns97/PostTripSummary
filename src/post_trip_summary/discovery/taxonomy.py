"""Controlled Vacation Blend theme taxonomy."""
from __future__ import annotations

from post_trip_summary.discovery.models import ThemeDefinition

THEMES: tuple[ThemeDefinition, ...] = (
    ThemeDefinition(id="road_trip", label="Road Trip", description="Frequent movement, scenic drives, many stops, changing locations"),
    ThemeDefinition(id="adventure_outdoors", label="Adventure", description="Hiking, boats, viewpoints, rugged terrain, active outdoor travel"),
    ThemeDefinition(id="nature_wildlife", label="Nature & Wildlife", description="Landscapes, animals, parks, gardens, natural features"),
    ThemeDefinition(id="culture_sightseeing", label="Culture & Sightseeing", description="Museums, architecture, historic sites, landmarks, neighborhoods"),
    ThemeDefinition(id="food_drink", label="Food & Drink", description="Restaurants, markets, cafes, wineries, breweries, cooking"),
    ThemeDefinition(id="people_social", label="People & Friends", description="Group photos, friends, family, social moments, portraits"),
    ThemeDefinition(id="nightlife_events", label="Nightlife & Events", description="Clubs, casinos, concerts, shows, evening venues, parties"),
    ThemeDefinition(id="beach_relaxation", label="Beach & Relaxation", description="Beach, pool, sun, slow days, resort downtime"),
    ThemeDefinition(id="resort_luxury", label="Resort & Luxury", description="Hotels, suites, spas, amenities, fine dining, premium experiences"),
    ThemeDefinition(id="family_milestone", label="Family & Milestones", description="Kids, reunions, anniversaries, birthdays, ceremonies"),
)

THEME_BY_ID = {theme.id: theme for theme in THEMES}


def validate_theme_ids(theme_ids: list[str]) -> None:
    unknown = sorted({theme_id for theme_id in theme_ids if theme_id not in THEME_BY_ID})
    if unknown:
        raise ValueError(f"unknown theme id: {', '.join(unknown)}")
