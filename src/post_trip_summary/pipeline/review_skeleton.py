# src/post_trip_summary/pipeline/review_skeleton.py
"""Stage 3: Interactive skeleton review in terminal."""
import os
import subprocess
import sys
import click
from datetime import datetime

from post_trip_summary.models import Trip, Day, Event


_TYPE_ICONS = {
    "landmark": "\U0001f4cd",
    "restaurant": "\U0001f37d",
    "hotel": "\U0001f3e8",
    "activity": "\U0001f3af",
    "transit": "\u2708",
    "unknown": "\u2753",
}


def _format_time(dt: datetime) -> str:
    try:
        return dt.strftime("%#I:%M %p")  # Windows
    except ValueError:
        return dt.strftime("%-I:%M %p")  # Unix


def format_event_line(event: Event, index: int) -> str:
    """Format a single event as a summary line."""
    icon = _TYPE_ICONS.get(event.type, "\u2753")
    start = _format_time(event.time_range[0])
    end = _format_time(event.time_range[1])
    photo_count = len(event.photos)
    sources = ", ".join(event.sources)

    line = f" {index:2d}. {icon} {event.name:<30s} {start}-{end}"
    if photo_count > 0:
        line += f"  ({photo_count} photos)"
    if sources:
        line += f"  [{sources}]"
    return line


def format_day_summary(day: Day, day_num: int) -> str:
    """Format a full day summary for display."""
    date_str = day.date.strftime("%B %d")
    header = f"-- Day {day_num}: {date_str} --------------"
    lines = [header]
    for i, event in enumerate(day.events, 1):
        lines.append(format_event_line(event, i))
    return "\n".join(lines)


def review_skeleton(trip: Trip) -> Trip:
    """Interactive loop: present each day, let user confirm or edit."""
    click.echo("\n=== Trip Skeleton Review ===\n")
    click.echo(f"Trip: {trip.name}")
    click.echo(f"Dates: {trip.date_range[0]} to {trip.date_range[1]}")
    click.echo(f"Total days: {len(trip.days)}\n")

    for day_num, day in enumerate(trip.days, 1):
        if not day.events:
            continue

        click.echo(format_day_summary(day, day_num))
        click.echo()

        while True:
            choice = click.prompt(
                "Does this look right? [y]es / [e]dit / [s]kip",
                type=str, default="y",
            ).lower().strip()

            if choice in ("y", "yes"):
                break
            elif choice in ("s", "skip"):
                break
            elif choice in ("e", "edit"):
                _edit_day(day, day_num)
                click.echo(format_day_summary(day, day_num))
                click.echo()
            else:
                click.echo("Please enter y, e, or s.")

    click.echo("\n=== Skeleton review complete ===\n")
    return trip


def _open_photo(photo_path) -> None:
    """Open a photo with the system default viewer."""
    path = str(photo_path)
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        click.echo(f"  Could not open photo: {e}")


def _edit_day(day: Day, day_num: int) -> None:
    """Let user edit events in a day."""
    click.echo("\nEditing options:")
    click.echo("  [r]ename <n> <new name>  -- rename event n")
    click.echo("  [m]erge <n>-<m>          -- merge events n through m into one")
    click.echo("  [v]iew <n>               -- open first photo for event n")
    click.echo("  [d]elete <n>             -- remove event n")
    click.echo("  [a]dd                    -- add a new event")
    click.echo("  [n]ote <n> <text>        -- add note to event n")
    click.echo("  [l]ist                   -- re-print the event list")
    click.echo("  [done]                   -- finish editing this day")

    while True:
        cmd = click.prompt("edit", type=str, default="done").strip()
        if cmd == "done":
            break

        parts = cmd.split(maxsplit=2)
        action = parts[0].lower() if parts else ""

        if action in ("r", "rename") and len(parts) >= 3:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(day.events):
                    day.events[idx].name = parts[2]
                    click.echo(f"  Renamed event {idx + 1} to '{parts[2]}'")
                else:
                    click.echo(f"  Invalid event number: {parts[1]}")
            except ValueError:
                click.echo("  Usage: rename <number> <new name>")

        elif action in ("d", "delete") and len(parts) >= 2:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(day.events):
                    removed = day.events.pop(idx)
                    click.echo(f"  Removed: {removed.name}")
                else:
                    click.echo(f"  Invalid event number: {parts[1]}")
            except ValueError:
                click.echo("  Usage: delete <number>")

        elif action in ("n", "note") and len(parts) >= 3:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(day.events):
                    day.events[idx].notes = parts[2]
                    click.echo(f"  Added note to event {idx + 1}")
                else:
                    click.echo(f"  Invalid event number: {parts[1]}")
            except ValueError:
                click.echo("  Usage: note <number> <text>")

        elif action in ("v", "view") and len(parts) >= 2:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(day.events):
                    event = day.events[idx]
                    if event.photos:
                        click.echo(f"  Opening first photo for '{event.name}' ({len(event.photos)} photos total)")
                        _open_photo(event.photos[0].path)
                    else:
                        click.echo(f"  Event '{event.name}' has no photos.")
                else:
                    click.echo(f"  Invalid event number: {parts[1]}")
            except ValueError:
                click.echo("  Usage: view <number>")

        elif action in ("m", "merge") and len(parts) >= 2:
            try:
                # Parse range like "3-6" or "3 6"
                range_str = parts[1]
                if "-" in range_str:
                    start_str, end_str = range_str.split("-", 1)
                elif len(parts) >= 3:
                    start_str, end_str = parts[1], parts[2]
                else:
                    click.echo("  Usage: merge <start>-<end>  (e.g. merge 3-8)")
                    continue

                start_idx = int(start_str) - 1
                end_idx = int(end_str) - 1

                if start_idx < 0 or end_idx >= len(day.events) or start_idx >= end_idx:
                    click.echo(f"  Invalid range. Must be between 1 and {len(day.events)}.")
                    continue

                to_merge = day.events[start_idx:end_idx + 1]
                names = sorted(set(e.name for e in to_merge if e.name not in ("Unknown", "")))
                suggested = ", ".join(names) if names else to_merge[0].name
                merged_name = click.prompt(f"  Name for merged event", default=suggested)

                # Combine into the first event
                merged = to_merge[0]
                merged.name = merged_name
                merged.time_range = (to_merge[0].time_range[0], to_merge[-1].time_range[1])
                for other in to_merge[1:]:
                    merged.photos.extend(other.photos)
                    merged.sources = list(set(merged.sources + other.sources))
                    if other.notes:
                        merged.notes = (merged.notes + " " + other.notes).strip()

                # Remove the merged-away events
                day.events[start_idx:end_idx + 1] = [merged]
                click.echo(f"  Merged {len(to_merge)} events into '{merged_name}' ({len(merged.photos)} photos)")

                # Redisplay
                click.echo()
                click.echo(format_day_summary(day, day_num))

            except ValueError:
                click.echo("  Usage: merge <start>-<end>  (e.g. merge 3-8)")

        elif action in ("l", "list"):
            click.echo()
            click.echo(format_day_summary(day, day_num))

        elif action in ("a", "add"):
            name = click.prompt("  Event name")
            event_type = click.prompt("  Type (landmark/restaurant/hotel/activity/transit/unknown)", default="unknown")
            from post_trip_summary.models import Location
            new_event = Event(
                id=f"day{day_num:02d}-event{len(day.events) + 1:02d}",
                type=event_type, name=name,
                time_range=(day.events[-1].time_range[1] if day.events else
                           datetime.combine(day.date, datetime.min.time()),
                           day.events[-1].time_range[1] if day.events else
                           datetime.combine(day.date, datetime.min.time())),
                location=Location(lat=0, lon=0, name=name, address=None, city="", country=""),
                photos=[], description="", notes="", sources=["manual"],
            )
            day.events.append(new_event)
            click.echo(f"  Added: {name}")

        else:
            click.echo("  Unknown command. Enter 'done' to finish.")
