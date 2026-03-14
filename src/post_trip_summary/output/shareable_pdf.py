# src/post_trip_summary/output/shareable_pdf.py
"""Generate the shareable PDF summary."""
from pathlib import Path
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip, Event


def compute_stats(trip: Trip) -> dict:
    """Compute fun stats for the summary."""
    all_events = [e for d in trip.days for e in d.events]
    all_photos = [p for e in all_events for p in e.photos]
    cities = {e.location.city for e in all_events if e.location.city}
    countries = {e.location.country for e in all_events if e.location.country}
    return {
        "days": (trip.date_range[1] - trip.date_range[0]).days + 1,
        "events": len(all_events),
        "photos": len(all_photos),
        "cities": len(cities),
        "countries": len(countries),
    }


def select_highlights(trip: Trip, max_count: int = 10) -> list[Event]:
    """Select the top events for the shareable summary."""
    all_events = [e for d in trip.days for e in d.events if e.type != "transit"]
    # Prefer events with descriptions and highlight photos
    scored = []
    for event in all_events:
        score = 0
        if event.description:
            score += 2
        if any(p.is_highlight for p in event.photos):
            score += 2
        if len(event.sources) >= 2:
            score += 1
        if event.notes:
            score += 1
        scored.append((score, event))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [event for _, event in scored[:max_count]]


def generate_shareable_pdf(trip: Trip, output_path: Path, map_image: str | None = None) -> None:
    """Render the shareable summary and convert to PDF."""
    from post_trip_summary.output.detailed_record import _format_time_filter
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    env.filters["ftime"] = _format_time_filter
    template = env.get_template("shareable_summary.html")

    highlights = select_highlights(trip)
    stats = compute_stats(trip)

    html = template.render(trip=trip, highlights=highlights, stats=stats, map_image=map_image)

    # Write HTML first
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    # Convert to PDF
    try:
        from weasyprint import HTML
        HTML(string=html, base_url=str(output_path.parent)).write_pdf(output_path)
    except Exception as e:
        import click
        click.echo(f"Warning: PDF generation failed ({e}). HTML version saved at {html_path}")
