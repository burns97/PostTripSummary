# src/post_trip_summary/pipeline/review_details.py
"""Stage 5: Interactive review of enriched event details."""
import click
from pathlib import Path

from post_trip_summary.models import Trip, Event, Photo


def _format_time(dt) -> str:
    try:
        return dt.strftime("%#I:%M %p")  # Windows
    except ValueError:
        return dt.strftime("%-I:%M %p")  # Unix


def format_event_detail(event: Event) -> str:
    """Format enriched event details for terminal display."""
    start = _format_time(event.time_range[0])
    end = _format_time(event.time_range[1])
    lines = [
        f"-- {event.name} ({start}-{end}) ----------",
        f"Type: {event.type}  |  Location: {event.location.city}, {event.location.country}",
    ]
    if event.description:
        lines.append(f"Description: {event.description}")
    if event.notes:
        lines.append(f"Notes: {event.notes}")

    total = len(event.photos)
    highlights = [p for p in event.photos if p.is_highlight]
    lines.append(f"Photos: {total} total, {len(highlights)} selected as highlights")

    for i, photo in enumerate(highlights, 1):
        desc = photo.ai_description or photo.path.name
        lines.append(f"  [{i}] {desc}  \u2605 highlight")

    lines.append(f"Sources: {', '.join(event.sources)}")
    return "\n".join(lines)


def review_details(trip: Trip) -> Trip:
    """Interactive loop: present enriched details event by event."""
    click.echo("\n=== Detail Review ===\n")

    for day in trip.days:
        for event in day.events:
            if not event.photos:
                continue

            click.echo(format_event_detail(event))
            click.echo()

            while True:
                choice = click.prompt(
                    "Accept? [y]es / [e]dit description / [n]ote / [p]hotos / [s]kip",
                    type=str, default="y",
                ).lower().strip()

                if choice in ("y", "yes"):
                    break
                elif choice in ("s", "skip"):
                    break
                elif choice in ("e", "edit"):
                    new_desc = click.prompt("New description", default=event.description)
                    event.description = new_desc
                    click.echo("  Updated description.")
                elif choice in ("n", "note"):
                    note = click.prompt("Add note", default=event.notes)
                    event.notes = note
                    click.echo("  Updated notes.")
                elif choice in ("p", "photos"):
                    _edit_photo_selection(event)
                    click.echo(format_event_detail(event))
                    click.echo()
                else:
                    click.echo("Please enter y, e, n, p, or s.")

    click.echo("\n=== Detail review complete ===\n")
    return trip


def _edit_photo_selection(event: Event) -> None:
    """Let user toggle highlight status of photos."""
    click.echo(f"\n  All photos for '{event.name}':")
    for i, photo in enumerate(event.photos, 1):
        marker = "\u2605" if photo.is_highlight else " "
        desc = photo.ai_description or photo.path.name
        click.echo(f"    {marker} [{i}] {desc}")

    click.echo("  Enter photo numbers to toggle (comma-separated), or 'done':")
    while True:
        inp = click.prompt("  toggle", type=str, default="done").strip()
        if inp == "done":
            break
        try:
            indices = [int(x.strip()) - 1 for x in inp.split(",")]
            for idx in indices:
                if 0 <= idx < len(event.photos):
                    event.photos[idx].is_highlight = not event.photos[idx].is_highlight
                    status = "\u2605" if event.photos[idx].is_highlight else "removed"
                    click.echo(f"    Photo {idx + 1}: {status}")
        except ValueError:
            click.echo("    Enter numbers separated by commas, or 'done'.")
