# src/post_trip_summary/output/detailed_record.py
"""Generate the detailed HTML trip record."""
from pathlib import Path
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip


def _format_time_filter(dt):
    """Jinja2 filter for cross-platform time formatting."""
    try:
        return dt.strftime("%#I:%M %p")  # Windows
    except ValueError:
        return dt.strftime("%-I:%M %p")  # Unix


def generate_detailed_record(trip: Trip, output_path: Path) -> None:
    """Render the detailed record HTML."""
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    env.filters["ftime"] = _format_time_filter
    template = env.get_template("detailed_record.html")
    html = template.render(trip=trip)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
