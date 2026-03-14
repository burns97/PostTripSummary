# src/post_trip_summary/preview/server.py
"""Local FastAPI preview server for trip outputs."""
import webbrowser
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip
from post_trip_summary.output.shareable_pdf import select_highlights, compute_stats
from post_trip_summary.output.detailed_record import _format_time_filter


def create_app(trip: Trip) -> FastAPI:
    """Create a FastAPI app for previewing trip outputs."""
    app = FastAPI(title="Post-Trip Summary Preview")
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    env.filters["ftime"] = _format_time_filter

    @app.get("/", response_class=HTMLResponse)
    def index():
        return f"""<html><body>
        <h1>Preview: {trip.name}</h1>
        <ul>
            <li><a href="/detailed">Detailed Record</a></li>
            <li><a href="/summary">Shareable Summary</a></li>
            <li><a href="/blog">Blog Post</a></li>
        </ul>
        </body></html>"""

    @app.get("/detailed", response_class=HTMLResponse)
    def detailed():
        template = env.get_template("detailed_record.html")
        return template.render(trip=trip)

    @app.get("/summary", response_class=HTMLResponse)
    def summary():
        template = env.get_template("shareable_summary.html")
        highlights = select_highlights(trip)
        stats = compute_stats(trip)
        return template.render(trip=trip, highlights=highlights, stats=stats, map_image=None)

    @app.get("/blog", response_class=HTMLResponse)
    def blog():
        template = env.get_template("blog_post.html")
        highlights = select_highlights(trip)
        return template.render(trip=trip, highlights=highlights)

    return app


def run_preview(trip: Trip, port: int = 8765) -> None:
    """Start the preview server and open browser."""
    import uvicorn
    import click

    app = create_app(trip)
    click.echo(f"\nPreview server starting at http://localhost:{port}")
    click.echo("Press Ctrl+C to stop.\n")
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
