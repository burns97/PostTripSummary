# src/post_trip_summary/pipeline/review_skeleton.py
"""Stage 3: Interactive skeleton review in terminal."""
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


def _edit_day(day: Day, day_num: int) -> None:
    """Let user edit events in a day."""
    click.echo("\nEditing options:")
    click.echo("  [r]ename <n> <new name>  -- rename event n")
    click.echo("  [d]elete <n>             -- remove event n")
    click.echo("  [a]dd                    -- add a new event")
    click.echo("  [n]ote <n> <text>        -- add note to event n")
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
