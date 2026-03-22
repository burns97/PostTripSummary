# src/post_trip_summary/pipeline/skeleton_ops.py
"""Pure functions for skeleton editing operations (merge, rename, delete, etc.)."""
from post_trip_summary.models import Day, Event


VALID_EVENT_TYPES = ["landmark", "restaurant", "hotel", "activity", "transit", "unknown"]


def merge_events(day: Day, event_ids: list[str]) -> Event:
    """Merge events matching event_ids within a day.

    Events must appear in the order they exist in day.events.
    Combines photos, extends time_range, unions sources, concatenates notes.
    Replaces the range in day.events with the single merged event.
    """
    indices = []
    for eid in event_ids:
        for i, ev in enumerate(day.events):
            if ev.id == eid:
                indices.append(i)
                break
        else:
            raise ValueError(f"Event '{eid}' not found in day")

    indices.sort()
    start, end = indices[0], indices[-1]
    to_merge = day.events[start:end + 1]

    merged = to_merge[0]
    merged.time_range = (to_merge[0].time_range[0], to_merge[-1].time_range[1])
    for other in to_merge[1:]:
        merged.photos.extend(other.photos)
        merged.sources = list(set(merged.sources + other.sources))
        if other.notes:
            merged.notes = (merged.notes + " " + other.notes).strip()

    day.events[start:end + 1] = [merged]
    return merged


def suggest_merge_name(events: list[Event]) -> str:
    """Suggest a name for merged events: sorted distinct non-Unknown names, comma-joined."""
    names = sorted(set(e.name for e in events if e.name not in ("Unknown", "")))
    return ", ".join(names) if names else events[0].name


def rename_event(event: Event, new_name: str) -> None:
    """Set event.name = new_name."""
    event.name = new_name


def delete_event(day: Day, event_id: str) -> Event:
    """Remove event by id from day.events. Returns the removed event."""
    for i, ev in enumerate(day.events):
        if ev.id == event_id:
            return day.events.pop(i)
    raise ValueError(f"Event '{event_id}' not found in day")


def change_event_type(event: Event, new_type: str) -> None:
    """Set event.type. Validates against known types."""
    if new_type not in VALID_EVENT_TYPES:
        raise ValueError(f"Invalid type '{new_type}'. Must be one of: {VALID_EVENT_TYPES}")
    event.type = new_type


def set_event_note(event: Event, note: str) -> None:
    """Set event.notes = note."""
    event.notes = note
