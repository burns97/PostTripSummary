"""FastAPI application factory for the wizard server."""
import asyncio
import io
import json as json_mod
from pathlib import Path
from pathlib import Path as FilePath

import jinja2
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sse_starlette.sse import EventSourceResponse

from post_trip_summary.config import SessionConfig, STAGES
from post_trip_summary.serialization import load_trip
from post_trip_summary.server.progress import ProgressTracker
from post_trip_summary.settings import get_vision_settings

THUMB_MAX_WIDTH = 300


def _serialize_event(event):
    """Serialize an event for JSON API responses."""
    return {
        "id": event.id,
        "name": event.name,
        "type": event.type,
        "time_range": f"{event.time_range[0].strftime('%H:%M')} - {event.time_range[1].strftime('%H:%M')}",
        "photo_count": len(event.photos),
        "sources": event.sources,
        "notes": event.notes or "",
        "thumb_urls": [f"/photos/{event.id}/{i}" for i in range(min(8, len(event.photos)))],
    }


def _build_event_index(trip):
    """Build {event_id: event} lookup dict."""
    if trip is None:
        return {}
    index = {}
    for day in trip.days:
        for event in day.events:
            index[event.id] = event
    return index


def _make_thumbnail(photo_path: FilePath) -> bytes:
    """Generate a JPEG thumbnail, handling HEIC/HEIF."""
    from PIL import Image

    suffix = photo_path.suffix.lower()
    if suffix in (".heic", ".heif"):
        import pillow_heif
        pillow_heif.register_heif_opener()
    img = Image.open(photo_path)
    img.thumbnail((THUMB_MAX_WIDTH, THUMB_MAX_WIDTH))
    if img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()

# Map stages to the wizard step the user should be on next
STAGE_TO_STEP = {
    "new": "setup",
    "setup": "setup",
    "ingested": "review",
    "reviewed": "enrich",
    "enriched": "highlights",
    "highlights_done": "generate",
    "generated": "generate",
}

WIZARD_STEPS = ["setup", "ingest", "review", "enrich", "highlights", "generate"]

STEP_COMPLETED_AT = {
    "setup": "ingested",
    "ingest": "ingested",
    "review": "reviewed",
    "enrich": "enriched",
    "highlights": "highlights_done",
    "generate": "generated",
}


def _get_wizard_context(session: SessionConfig) -> dict:
    """Build template context for the wizard step indicator."""
    current_step = STAGE_TO_STEP.get(session.current_stage, "setup")
    stage_idx = STAGES.index(session.current_stage)
    completed_steps = set()
    for step, completed_stage in STEP_COMPLETED_AT.items():
        if completed_stage in STAGES:
            if STAGES.index(completed_stage) <= stage_idx:
                completed_steps.add(step)
    return {
        "session": session,
        "current_step": current_step,
        "completed_steps": completed_steps,
    }


def _load_trip_for_stage(session: SessionConfig):
    """Load the most recent trip data based on current stage, or None."""
    stage_idx = STAGES.index(session.current_stage)
    for i in range(stage_idx, -1, -1):
        stage = STAGES[i]
        try:
            path = session.stage_file(stage)
            if path.exists():
                return load_trip(path)
        except ValueError:
            continue
    return None


def create_app(session: SessionConfig) -> FastAPI:
    """Create the wizard FastAPI app for a session."""
    app = FastAPI(title="Post-Trip Summary Wizard")
    app.state.session = session
    app.state.trip = _load_trip_for_stage(session)
    app.state.thumb_cache = {}
    app.state.background_task = None
    app.state.event_index = _build_event_index(app.state.trip)

    env = jinja2.Environment(
        loader=jinja2.PackageLoader("post_trip_summary", "templates"),
        autoescape=True,
    )

    @app.get("/api/stage/current")
    def get_current_stage():
        return JSONResponse({
            "stage": app.state.session.current_stage,
            "name": app.state.session.name,
            "slug": app.state.session.slug,
        })

    @app.get("/")
    def root_redirect():
        current_step = STAGE_TO_STEP.get(app.state.session.current_stage, "setup")
        return RedirectResponse(url=f"/wizard/{current_step}")

    @app.get("/wizard/setup")
    def wizard_setup():
        ctx = _get_wizard_context(app.state.session)
        vs = get_vision_settings()
        ctx["vision_provider"] = app.state.session.settings.get(
            "vision_provider", vs.get("provider", "gemini")
        )
        ctx["api_key_set"] = bool(vs.get("api_key"))
        template = env.get_template("setup.html")
        return HTMLResponse(template.render(**ctx))

    @app.post("/api/session/inputs")
    async def update_session_inputs(request: Request):
        request_body = await request.json()
        inputs = request_body.get("inputs", {})
        settings = request_body.get("settings", {})

        # Validate photos path exists if provided
        photos_path = inputs.get("photos", "")
        if photos_path:
            if not Path(photos_path).is_dir():
                raise HTTPException(422, f"Photos directory not found: {photos_path}")

        # Validate optional source paths exist if provided
        for key in ["excel", "credit_card", "google_maps", "apple_health", "dayone"]:
            path = inputs.get(key, "")
            if path:
                if not Path(path).exists():
                    raise HTTPException(422, f"File not found: {path}")

        # Update session
        app.state.session.inputs.update(inputs)
        if "vision_provider" in settings:
            app.state.session.settings["vision_provider"] = settings["vision_provider"]

        if app.state.session.current_stage == "new":
            app.state.session.current_stage = "setup"

        app.state.session.save()
        return JSONResponse({"status": "ok"})

    @app.get("/photos/{event_id}/{photo_idx}")
    def serve_photo_by_event(event_id: str, photo_idx: int):
        event = app.state.event_index.get(event_id)
        if not event or photo_idx >= len(event.photos):
            raise HTTPException(404, "Photo not found")
        photo = event.photos[photo_idx]
        cache_key = (event_id, photo_idx)
        if cache_key not in app.state.thumb_cache:
            app.state.thumb_cache[cache_key] = _make_thumbnail(photo.path)
        return Response(content=app.state.thumb_cache[cache_key], media_type="image/jpeg")

    @app.get("/photos/{filename}")
    def serve_photo_by_name(filename: str):
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        stem = FilePath(filename).stem
        for day in app.state.trip.days:
            for event in day.events:
                for photo in event.photos:
                    if photo.path.stem == stem:
                        cache_key = ("name", stem)
                        if cache_key not in app.state.thumb_cache:
                            app.state.thumb_cache[cache_key] = _make_thumbnail(photo.path)
                        return Response(content=app.state.thumb_cache[cache_key], media_type="image/jpeg")
        raise HTTPException(404, f"Photo not found: {filename}")

    @app.post("/api/stage/start")
    async def start_stage(request: Request):
        body = await request.json()
        stage = body.get("stage")
        if stage != "ingest":
            raise HTTPException(400, f"Unknown stage: {stage}")

        # Reject if a task is already running
        if app.state.background_task is not None and not app.state.background_task.done():
            return JSONResponse({"status": "already_running"}, status_code=409)

        tracker = ProgressTracker()
        app.state.progress = tracker

        async def _run():
            try:
                from post_trip_summary.server.compute import run_ingest_pipeline
                trip = await asyncio.to_thread(
                    run_ingest_pipeline, app.state.session, tracker.callback()
                )
                app.state.trip = trip
                app.state.event_index = _build_event_index(trip)
                app.state.session.current_stage = "ingested"
                app.state.session.save()
                tracker.complete("review")
            except Exception as e:
                tracker.fail(str(e))

        app.state.background_task = asyncio.create_task(_run())
        return JSONResponse({"status": "started"})

    @app.get("/api/progress")
    async def progress_stream():
        tracker = getattr(app.state, "progress", None)

        async def _generate():
            if tracker is None:
                yield {"event": "state", "data": json_mod.dumps({"done": True, "phase": "idle"})}
                return
            while True:
                state = tracker.get_state()
                yield {"event": "state", "data": json_mod.dumps(state)}
                if state.get("done") or state.get("failed"):
                    return
                await asyncio.sleep(0.5)

        return EventSourceResponse(_generate())

    @app.get("/wizard/ingest", response_class=HTMLResponse)
    def wizard_ingest():
        # If ingest already completed, redirect to the next step
        if app.state.session.current_stage not in ("setup", "new"):
            step = STAGE_TO_STEP.get(app.state.session.current_stage, "review")
            if step != "ingest":
                return RedirectResponse(f"/wizard/{step}", status_code=307)

        ctx = _get_wizard_context(app.state.session)
        ctx["stage_title"] = "Processing Trip Data"
        ctx["compute_stage"] = "ingest"
        ctx["auto_start"] = app.state.session.current_stage == "setup"
        template = env.get_template("progress.html")
        return template.render(**ctx)

    def _save_trip():
        """Persist current trip state."""
        from post_trip_summary.serialization import save_trip as _save
        stage = app.state.session.current_stage
        if stage in ("ingested", "reviewed"):
            _save(app.state.trip, app.state.session.stage_file("reviewed"))
        else:
            _save(app.state.trip, app.state.session.stage_file(stage))

    def _rebuild_index():
        """Rebuild event index and clear thumbnail cache after structural changes."""
        app.state.event_index = _build_event_index(app.state.trip)
        app.state.thumb_cache.clear()

    # --- Skeleton editing endpoints ---

    @app.post("/api/skeleton/merge")
    async def skeleton_merge(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import merge_events
        body = await request.json()
        day_index = body.get("day_index")
        event_ids = body.get("event_ids", [])
        if day_index is None or len(event_ids) < 2:
            raise HTTPException(400, "day_index and at least 2 event_ids required")
        trip = app.state.trip
        if trip is None or day_index >= len(trip.days):
            raise HTTPException(404, "Day not found")
        day = trip.days[day_index]
        try:
            merged = merge_events(day, event_ids)
        except ValueError as e:
            raise HTTPException(400, str(e))
        _rebuild_index()
        _save_trip()
        return JSONResponse({"merged_event": _serialize_event(merged)})

    @app.post("/api/skeleton/rename")
    async def skeleton_rename(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import rename_event
        body = await request.json()
        event_id = body.get("event_id")
        new_name = body.get("new_name", "").strip()
        if not event_id or not new_name:
            raise HTTPException(400, "event_id and new_name required")
        event = app.state.event_index.get(event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        rename_event(event, new_name)
        _save_trip()
        return JSONResponse({"event_id": event_id, "new_name": new_name})

    @app.post("/api/skeleton/delete")
    async def skeleton_delete(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import delete_event
        body = await request.json()
        event_id = body.get("event_id")
        day_index = body.get("day_index")
        if event_id is None or day_index is None:
            raise HTTPException(400, "event_id and day_index required")
        trip = app.state.trip
        if trip is None or day_index >= len(trip.days):
            raise HTTPException(404, "Day not found")
        day = trip.days[day_index]
        try:
            delete_event(day, event_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
        _rebuild_index()
        _save_trip()
        return JSONResponse({"deleted": event_id})

    @app.post("/api/skeleton/update-type")
    async def skeleton_update_type(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import change_event_type
        body = await request.json()
        event_id = body.get("event_id")
        new_type = body.get("new_type", "").strip()
        if not event_id or not new_type:
            raise HTTPException(400, "event_id and new_type required")
        event = app.state.event_index.get(event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        try:
            change_event_type(event, new_type)
        except ValueError as e:
            raise HTTPException(400, str(e))
        _save_trip()
        return JSONResponse({"event_id": event_id, "new_type": new_type})

    @app.post("/api/skeleton/add-note")
    async def skeleton_add_note(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import set_event_note
        body = await request.json()
        event_id = body.get("event_id")
        note = body.get("note", "")
        if not event_id:
            raise HTTPException(400, "event_id required")
        event = app.state.event_index.get(event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        set_event_note(event, note)
        _save_trip()
        return JSONResponse({"event_id": event_id, "note": note})

    @app.post("/api/skeleton/suggest-merge-name")
    async def skeleton_suggest_merge_name(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import suggest_merge_name
        body = await request.json()
        event_ids = body.get("event_ids", [])
        if len(event_ids) < 2:
            raise HTTPException(400, "At least 2 event_ids required")
        events = [app.state.event_index.get(eid) for eid in event_ids]
        if any(e is None for e in events):
            raise HTTPException(404, "One or more events not found")
        name = suggest_merge_name(events)
        return JSONResponse({"suggested_name": name})

    # --- Photo review endpoints ---

    @app.post("/api/toggle-keep")
    async def toggle_keep(request: Request):
        body = await request.json()
        event_id = body.get("event_id")
        photo_index = body.get("photo_index")
        if event_id is None or photo_index is None:
            raise HTTPException(400, "event_id and photo_index required")
        event = app.state.event_index.get(event_id)
        if not event or photo_index >= len(event.photos):
            raise HTTPException(404, "Photo not found")
        photo = event.photos[photo_index]
        photo.is_kept = not photo.is_kept
        _save_trip()
        return JSONResponse({"event_id": event_id, "photo_index": photo_index, "is_kept": photo.is_kept})

    @app.post("/api/bulk-action")
    async def bulk_action(request: Request):
        body = await request.json()
        event_id = body.get("event_id")
        action = body.get("action")
        if not event_id or action not in ("keep_all", "remove_all"):
            raise HTTPException(400, "event_id and action (keep_all|remove_all) required")
        event = app.state.event_index.get(event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        keep = action == "keep_all"
        for photo in event.photos:
            photo.is_kept = keep
        _save_trip()
        return JSONResponse({"event_id": event_id, "action": action, "photo_count": len(event.photos)})

    # --- Description editing ---

    @app.post("/api/update-description")
    async def update_description(request: Request):
        body = await request.json()
        event_id = body.get("event_id")
        description = body.get("description", "")
        if not event_id:
            raise HTTPException(400, "event_id required")
        event = app.state.event_index.get(event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        event.description = description
        _save_trip()
        return JSONResponse({"event_id": event_id, "description": description})

    # --- Stage advancement ---

    @app.post("/api/stage/advance")
    async def advance_stage(request: Request):
        current = app.state.session.current_stage
        idx = STAGES.index(current)
        if idx + 1 < len(STAGES):
            app.state.session.current_stage = STAGES[idx + 1]
            app.state.session.save()
            _save_trip()
        step = STAGE_TO_STEP.get(app.state.session.current_stage, "review")
        return JSONResponse({"stage": app.state.session.current_stage, "next_step": step})

    # Placeholder routes for remaining wizard steps
    for step_name in ["review", "enrich", "highlights", "generate"]:
        _register_placeholder_step(app, env, step_name)

    return app


def _register_placeholder_step(app: FastAPI, env: jinja2.Environment, step_name: str):
    """Register a placeholder wizard step route."""
    template_str = (
        '{% extends "wizard.html" %}\n'
        "{% block content %}"
        "<h1>" + step_name.title() + "</h1>"
        "<p>This step is not yet implemented.</p>"
        "{% endblock %}"
    )
    # Store the template string and step name in a closure — avoid passing
    # Jinja2 Template objects as default args (FastAPI deepcopy breaks them)
    _tpl_str = template_str
    _name = step_name

    @app.get(f"/wizard/{step_name}", name=f"wizard_{step_name}")
    def wizard_placeholder():
        compiled = env.from_string(_tpl_str)
        ctx = _get_wizard_context(app.state.session)
        return HTMLResponse(compiled.render(**ctx))
