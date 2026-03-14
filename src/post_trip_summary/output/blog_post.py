# src/post_trip_summary/output/blog_post.py
"""Generate blog-ready HTML."""
from pathlib import Path
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip
from post_trip_summary.output.shareable_pdf import select_highlights


def generate_blog_post(trip: Trip, output_path: Path) -> None:
    """Render a blog-friendly HTML file."""
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    template = env.get_template("blog_post.html")
    highlights = select_highlights(trip)
    html = template.render(trip=trip, highlights=highlights)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
