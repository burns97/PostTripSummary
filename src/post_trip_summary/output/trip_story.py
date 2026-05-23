"""Generate the polished Trip Story HTML output."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from post_trip_summary.models import Day, Event, Photo, Trip


def _all_events(trip: Trip) -> list[Event]:
    return [event for day in trip.days for event in day.events]


def _is_transit_event(event: Event) -> bool:
    return (event.type or "").lower() == "transit"


def _location_story_events(trip: Trip) -> list[Event]:
    return [event for event in _all_events(trip) if not _is_transit_event(event)]


def _kept_photos(event: Event) -> list[Photo]:
    return [photo for photo in event.photos if photo.is_kept]


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def select_highlight_photos(trip: Trip, max_count: int = 12) -> list[Photo]:
    """Return kept highlight photos in trip order."""
    photos = [
        photo
        for event in _all_events(trip)
        for photo in event.photos
        if photo.is_kept and photo.is_highlight
    ]
    return photos[:max_count]


def select_cover_photo(trip: Trip) -> Photo | None:
    """Choose the best cover photo using Phase 1 defaults."""
    kept_highlights = [
        photo
        for event in _all_events(trip)
        for photo in event.photos
        if photo.is_kept and photo.is_highlight
    ]
    if kept_highlights:
        return max(
            kept_highlights,
            key=lambda photo: photo.quality_score if photo.quality_score is not None else -1,
        )

    for event in _all_events(trip):
        kept = _kept_photos(event)
        if kept:
            return kept[0]
    return None


def compute_story_stats(trip: Trip) -> dict[str, int]:
    """Compute story-facing stats from kept photos and all timeline events."""
    events = _all_events(trip)
    location_events = _location_story_events(trip)
    kept_photos = [photo for event in events for photo in event.photos if photo.is_kept]
    highlights = [photo for photo in kept_photos if photo.is_highlight]
    cities = {event.location.city for event in location_events if event.location.city}
    countries = {event.location.country for event in location_events if event.location.country}
    return {
        "days": (trip.date_range[1] - trip.date_range[0]).days + 1,
        "stops": len(events),
        "photos": len(kept_photos),
        "highlights": len(highlights),
        "cities": len(cities),
        "countries": len(countries),
    }


def build_location_summary(trip: Trip) -> str:
    """Build a compact location summary for the story cover."""
    events = _location_story_events(trip)
    countries = _ordered_unique([event.location.country for event in events if event.location.country])
    cities = _ordered_unique([event.location.city for event in events if event.location.city])

    if len(countries) == 1 and len(cities) == 1:
        return f"{cities[0]}, {countries[0]}"
    if len(countries) == 1 and cities:
        if len(cities) <= 3:
            return f"{', '.join(cities)}, {countries[0]}"
        return f"{len(cities)} cities in {countries[0]}"
    if countries:
        return ", ".join(countries[:3]) if len(countries) <= 3 else f"{len(countries)} countries"
    if cities:
        return ", ".join(cities[:3])
    return ""


def _event_has_story_content(event: Event) -> bool:
    return bool(event.description or event.notes or _kept_photos(event))


def days_with_story_content(trip: Trip) -> list[Day]:
    """Return days that have at least one event worth showing in the story."""
    return [
        day
        for day in trip.days
        if any(_event_has_story_content(event) for event in day.events)
    ]


def build_story_context(trip: Trip, map_image: str | None = None) -> dict:
    """Build the template context for Trip Story rendering."""
    return {
        "trip": trip,
        "cover_photo": select_cover_photo(trip),
        "location_summary": build_location_summary(trip),
        "stats": compute_story_stats(trip),
        "highlight_photos": select_highlight_photos(trip),
        "story_days": days_with_story_content(trip),
        "map_image": map_image,
    }


def generate_trip_story(trip: Trip, output_path: Path, map_image: str | None = None) -> None:
    """Render the Trip Story HTML output."""
    from post_trip_summary.output.detailed_record import _format_time_filter, _photo_url_filter

    env = Environment(
        loader=PackageLoader("post_trip_summary", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["ftime"] = _format_time_filter
    env.filters["photo_url"] = _photo_url_filter
    template = env.get_template("trip_story.html")
    html = template.render(**build_story_context(trip, map_image=map_image))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
