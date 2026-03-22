# src/post_trip_summary/preview/server.py
"""Local FastAPI preview server for trip outputs and photo review."""
import io
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip
from post_trip_summary.output.shareable_pdf import select_highlights, compute_stats
from post_trip_summary.output.detailed_record import _format_time_filter, _photo_url_filter
from post_trip_summary.pipeline.review_skeleton import _TYPE_ICONS


def _build_event_index(trip: Trip) -> dict:
    """Build {event_id: event} lookup for O(1) access."""
    return {
        event.id: event
        for day in trip.days
        for event in day.events
    }


# Thumbnail cache: (event_id, photo_index) -> JPEG bytes
_thumb_cache: dict[tuple[str, int], bytes] = {}

THUMB_MAX_WIDTH = 300


def _make_thumbnail(photo_path: Path) -> bytes:
    """Open image (including HEIC), resize to thumbnail, return JPEG bytes."""
    from PIL import Image
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass

    img = Image.open(photo_path)
    if img.width > THUMB_MAX_WIDTH:
        ratio = THUMB_MAX_WIDTH / img.width
        new_size = (THUMB_MAX_WIDTH, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Convert to RGB if needed (HEIC can be RGBA, etc.)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _serialize_event(event) -> dict:
    """Serialize an event for JSON API responses."""
    return {
        "id": event.id,
        "name": event.name,
        "type": event.type,
        "time_range": f"{_format_time_filter(event.time_range[0])} – {_format_time_filter(event.time_range[1])}",
        "photo_count": len(event.photos),
        "sources": event.sources,
        "notes": event.notes,
        "thumb_urls": [f"/photos/{event.id}/{i}" for i in range(min(len(event.photos), 8))],
    }


def create_app(trip: Trip, save_fn=None) -> FastAPI:
    """Create a FastAPI app for previewing trip outputs and reviewing photos.

    Args:
        trip: The trip data.
        save_fn: Optional callable to persist trip changes (for review modes).
    """
    app = FastAPI(title="Post-Trip Summary Preview")
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    env.filters["ftime"] = _format_time_filter
    env.filters["photo_url"] = _photo_url_filter

    # Mutable state container so API handlers can rebuild after structural mutations
    state = {"event_index": _build_event_index(trip)}

    def _get_event(event_id):
        return state["event_index"].get(event_id)

    def _rebuild_index():
        state["event_index"] = _build_event_index(trip)
        _thumb_cache.clear()

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

    # --- Photo serving ---

    # Build stem -> photo path lookup for output-style URLs (photos/<stem>.jpg)
    def _build_photo_by_stem():
        index = {}
        for day in trip.days:
            for event in day.events:
                for photo in event.photos:
                    index[photo.path.stem] = photo.path
        return index

    state["photo_by_stem"] = _build_photo_by_stem()

    @app.get("/photos/{filename}")
    def serve_photo_by_name(filename: str):
        """Serve photos by filename (used by output preview templates)."""
        stem = filename.rsplit(".", 1)[0] if "." in filename else filename
        cache_key = ("by_name", stem)
        if cache_key in _thumb_cache:
            return Response(content=_thumb_cache[cache_key], media_type="image/jpeg")

        photo_path = state["photo_by_stem"].get(stem)
        if not photo_path or not photo_path.exists():
            return Response(status_code=404)

        try:
            jpeg_bytes = _make_thumbnail(photo_path)
            _thumb_cache[cache_key] = jpeg_bytes
            return Response(content=jpeg_bytes, media_type="image/jpeg")
        except Exception:
            return Response(status_code=500)

    @app.get("/photos/{event_id}/{photo_idx}")
    def serve_photo(event_id: str, photo_idx: int):
        cache_key = (event_id, photo_idx)
        if cache_key in _thumb_cache:
            return Response(content=_thumb_cache[cache_key], media_type="image/jpeg")

        event = _get_event(event_id)
        if not event or photo_idx < 0 or photo_idx >= len(event.photos):
            return Response(status_code=404)

        photo = event.photos[photo_idx]
        if not photo.path.exists():
            return Response(status_code=404)

        try:
            jpeg_bytes = _make_thumbnail(photo.path)
            _thumb_cache[cache_key] = jpeg_bytes
            return Response(content=jpeg_bytes, media_type="image/jpeg")
        except Exception:
            return Response(status_code=500)

    # --- Photo review routes ---

    @app.get("/review/cull", response_class=HTMLResponse)
    def review_cull():
        template = env.get_template("photo_review.html")
        return template.render(trip=trip, mode="cull")

    @app.get("/review/highlights", response_class=HTMLResponse)
    def review_highlights():
        template = env.get_template("photo_review.html")
        return template.render(trip=trip, mode="highlights")

    @app.post("/api/toggle-keep")
    async def toggle_keep(request: Request):
        data = await request.json()
        event = _get_event(data["event_id"])
        if not event:
            return JSONResponse({"error": "event not found"}, status_code=404)
        idx = data["photo_index"]
        if idx < 0 or idx >= len(event.photos):
            return JSONResponse({"error": "invalid photo index"}, status_code=400)
        photo = event.photos[idx]
        photo.is_kept = not photo.is_kept
        if save_fn:
            save_fn(trip)
        kept = sum(1 for p in event.photos if p.is_kept)
        return {"is_kept": photo.is_kept, "kept_count": kept, "total": len(event.photos)}

    @app.post("/api/toggle-highlight")
    async def toggle_highlight(request: Request):
        data = await request.json()
        event = _get_event(data["event_id"])
        if not event:
            return JSONResponse({"error": "event not found"}, status_code=404)
        idx = data["photo_index"]
        if idx < 0 or idx >= len(event.photos):
            return JSONResponse({"error": "invalid photo index"}, status_code=400)
        photo = event.photos[idx]
        photo.is_highlight = not photo.is_highlight
        if save_fn:
            save_fn(trip)
        highlighted = sum(1 for p in event.photos if p.is_kept and p.is_highlight)
        kept = sum(1 for p in event.photos if p.is_kept)
        return {"is_highlight": photo.is_highlight, "highlighted_count": highlighted, "kept_count": kept}

    @app.post("/api/bulk-action")
    async def bulk_action(request: Request):
        data = await request.json()
        event = _get_event(data["event_id"])
        if not event:
            return JSONResponse({"error": "event not found"}, status_code=404)
        action = data["action"]
        count = 0
        if action == "keep_all":
            for p in event.photos:
                p.is_kept = True
                count += 1
        elif action == "remove_all":
            for p in event.photos:
                p.is_kept = False
                count += 1
        elif action == "highlight_all":
            for p in event.photos:
                if p.is_kept:
                    p.is_highlight = True
                    count += 1
        elif action == "highlight_none":
            for p in event.photos:
                p.is_highlight = False
                count += 1
        else:
            return JSONResponse({"error": "unknown action"}, status_code=400)
        if save_fn:
            save_fn(trip)
        kept = sum(1 for p in event.photos if p.is_kept)
        highlighted = sum(1 for p in event.photos if p.is_kept and p.is_highlight)
        return {"action": action, "affected": count, "kept_count": kept,
                "highlighted_count": highlighted, "total": len(event.photos)}

    # --- Skeleton review routes ---

    @app.get("/review/skeleton", response_class=HTMLResponse)
    def review_skeleton_page():
        template = env.get_template("skeleton_review.html")
        return template.render(trip=trip, type_icons=_TYPE_ICONS)

    @app.post("/api/skeleton/merge")
    async def skeleton_merge(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import merge_events
        data = await request.json()
        day_index = data["day_index"]
        event_ids = data["event_ids"]
        new_name = data["new_name"]

        if day_index < 0 or day_index >= len(trip.days):
            return JSONResponse({"error": "invalid day_index"}, status_code=400)

        day = trip.days[day_index]
        try:
            merged = merge_events(day, event_ids)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        merged.name = new_name
        _rebuild_index()
        if save_fn:
            save_fn(trip)

        return {
            "merged_event": _serialize_event(merged),
            "day_events": [_serialize_event(e) for e in day.events],
        }

    @app.post("/api/skeleton/rename")
    async def skeleton_rename(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import rename_event
        data = await request.json()
        event = _get_event(data["event_id"])
        if not event:
            return JSONResponse({"error": "event not found"}, status_code=404)
        rename_event(event, data["new_name"])
        if save_fn:
            save_fn(trip)
        return {"event_id": event.id, "new_name": event.name}

    @app.post("/api/skeleton/delete")
    async def skeleton_delete(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import delete_event
        data = await request.json()
        event_id = data["event_id"]

        # Find which day contains this event
        target_day = None
        day_index = -1
        for i, day in enumerate(trip.days):
            for ev in day.events:
                if ev.id == event_id:
                    target_day = day
                    day_index = i
                    break
            if target_day:
                break

        if not target_day:
            return JSONResponse({"error": "event not found"}, status_code=404)

        try:
            removed = delete_event(target_day, event_id)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        _rebuild_index()
        if save_fn:
            save_fn(trip)
        return {
            "deleted": removed.id,
            "day_index": day_index,
            "remaining_events": len(target_day.events),
        }

    @app.post("/api/skeleton/update-type")
    async def skeleton_update_type(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import change_event_type
        data = await request.json()
        event = _get_event(data["event_id"])
        if not event:
            return JSONResponse({"error": "event not found"}, status_code=404)
        try:
            change_event_type(event, data["new_type"])
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        if save_fn:
            save_fn(trip)
        return {"event_id": event.id, "new_type": event.type}

    @app.post("/api/skeleton/add-note")
    async def skeleton_add_note(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import set_event_note
        data = await request.json()
        event = _get_event(data["event_id"])
        if not event:
            return JSONResponse({"error": "event not found"}, status_code=404)
        set_event_note(event, data["note"])
        if save_fn:
            save_fn(trip)
        return {"event_id": event.id, "note": event.notes}

    @app.post("/api/skeleton/suggest-merge-name")
    async def skeleton_suggest_merge_name(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import suggest_merge_name
        data = await request.json()
        events = [_get_event(eid) for eid in data["event_ids"]]
        events = [e for e in events if e is not None]
        if len(events) < 2:
            return JSONResponse({"error": "need at least 2 valid events"}, status_code=400)
        return {"suggested_name": suggest_merge_name(events)}

    return app


def run_preview(trip: Trip, port: int = 8765, save_fn=None, open_path: str = "/") -> None:
    """Start the preview server and open browser."""
    import uvicorn
    import click

    app = create_app(trip, save_fn=save_fn)
    click.echo(f"\nServer starting at http://localhost:{port}")
    click.echo("Press Ctrl+C to stop.\n")
    webbrowser.open(f"http://localhost:{port}{open_path}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
