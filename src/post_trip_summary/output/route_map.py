"""Shared route map generation helpers."""
from __future__ import annotations

from pathlib import Path

from post_trip_summary.models import Event, Trip


def include_route_map_event(event: Event) -> bool:
    """Return whether an event should appear as a route-map stop."""
    if (event.type or "").lower() == "transit":
        return False
    return event.location.lat is not None and event.location.lon is not None


def route_map_events(trip: Trip) -> list[Event]:
    """Return story-facing route map stops in trip order."""
    return [
        event
        for day in trip.days
        for event in day.events
        if include_route_map_event(event)
    ]


def generate_static_route_map(trip: Trip, output_dir: Path) -> str | None:
    """Generate a static route map image and return its relative path."""
    from staticmap import CircleMarker, StaticMap

    route_events = route_map_events(trip)
    if not route_events:
        return None

    m = StaticMap(800, 400)
    for event in route_events:
        m.add_marker(CircleMarker((event.location.lon, event.location.lat), "#e74c3c", 8))

    map_path = output_dir / "route-map.png"
    image = m.render()
    image.save(str(map_path))
    return "route-map.png"
