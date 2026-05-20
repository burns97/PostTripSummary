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
from post_trip_summary.output.detailed_record import _format_time_filter, _photo_url_filter
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
        "name_candidates": getattr(event, "name_candidates", {}),
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
    "reviewed": "discovery",
    "discovered": "enrich",
    "enriched": "highlights",
    "highlights_done": "generate",
    "generated": "generate",
}

WIZARD_STEPS = ["setup", "ingest", "review", "discovery", "enrich", "highlights", "generate"]

STEP_COMPLETED_AT = {
    "setup": "ingested",
    "ingest": "ingested",
    "review": "reviewed",
    "discovery": "discovered",
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
    env.filters["ftime"] = _format_time_filter
    env.filters["photo_url"] = _photo_url_filter

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

    @app.get("/api/enrich/estimate")
    def enrich_estimate():
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        from post_trip_summary.vision.client import create_provider as _create_provider
        vs = get_vision_settings()

        # Collect all events with photos
        all_events = [e for d in app.state.trip.days for e in d.events if e.photos]

        # Montage-based counting: separate montage events (>3 kept) from few-photo events (<=3 kept)
        montage_events = []
        few_photo_calls = 0

        for event in all_events:
            kept_photos = [p for p in event.photos if p.is_kept]
            if len(kept_photos) > 3:
                montage_events.append(event)
            else:
                few_photo_calls += len(kept_photos)

        # Quick mode: montage event count (one call per montage event) + few-photo individual calls
        quick_total = len(montage_events) + few_photo_calls

        # Thorough mode: quick + (montage_events * 5 for highlights per-photo calls) + montage_events for synthesis
        thorough_total = quick_total + (len(montage_events) * 5) + len(montage_events)

        quick_cost = 0.0
        thorough_cost = 0.0
        billing = vs.get("billing", False)
        if vs.get("api_key") and billing:
            try:
                provider = _create_provider(
                    vs["provider"], api_key=vs.get("api_key"), model=vs.get("model"),
                    billing=billing,
                )
                quick_cost = provider.estimate_cost(quick_total)
                thorough_cost = provider.estimate_cost(thorough_total)
            except Exception:
                pass

        return JSONResponse({
            "provider": vs.get("provider", "gemini"),
            "model": vs.get("model", ""),
            "total_images": quick_total,
            "reduced_images": thorough_total,
            "estimated_cost": quick_cost,
            "thorough_cost": thorough_cost,
            "billing": billing,
            "has_api_key": bool(vs.get("api_key")),
            "event_count": len(all_events),
        })

    @app.post("/api/stage/start")
    async def start_stage(request: Request):
        body = await request.json()
        stage = body.get("stage")

        # Reject if a task is already running
        if app.state.background_task is not None and not app.state.background_task.done():
            return JSONResponse({"status": "already_running"}, status_code=409)

        if stage == "ingest":
            tracker = ProgressTracker()
            app.state.progress = tracker

            async def _run_ingest():
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
                finally:
                    app.state.background_task = None

            app.state.background_task = asyncio.create_task(_run_ingest())
            return JSONResponse({"status": "started"})

        elif stage == "enrich":
            from post_trip_summary.discovery.serialization import vacation_blend_path

            artifact_path = vacation_blend_path(app.state.session.session_dir)
            if (
                app.state.session.current_stage != "discovered"
                or not artifact_path.exists()
            ):
                raise HTTPException(409, "Discovery must be completed first")

            mode = body.get("mode", "quick")
            tracker = ProgressTracker()
            app.state.progress = tracker

            async def _run_enrich():
                try:
                    from post_trip_summary.server.compute import run_enrich_pipeline
                    trip = await asyncio.to_thread(
                        run_enrich_pipeline, app.state.session, mode, tracker.callback()
                    )
                    app.state.trip = trip
                    app.state.event_index = _build_event_index(trip)
                    app.state.session.current_stage = "enriched"
                    app.state.session.save()
                    tracker.complete("highlights")
                except Exception as e:
                    tracker.fail(str(e))
                finally:
                    app.state.background_task = None

            app.state.background_task = asyncio.create_task(_run_enrich())
            return JSONResponse({"status": "started"})

        elif stage == "synthesize":
            tracker = ProgressTracker()
            app.state.progress = tracker

            async def _run_synthesize():
                try:
                    from post_trip_summary.server.compute import run_synthesis_pipeline
                    trip = await asyncio.to_thread(
                        run_synthesis_pipeline, app.state.session, tracker.callback()
                    )
                    app.state.trip = trip
                    app.state.event_index = _build_event_index(trip)
                    app.state.session.current_stage = "highlights_done"
                    app.state.session.save()
                    tracker.complete("generate")
                except Exception as e:
                    tracker.fail(str(e))
                finally:
                    app.state.background_task = None

            app.state.background_task = asyncio.create_task(_run_synthesize())
            return JSONResponse({"status": "started"})

        else:
            raise HTTPException(400, f"Unknown stage: {stage}")

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
        """Persist current trip state to the appropriate stage file."""
        from post_trip_summary.serialization import save_trip as _save
        stage = app.state.session.current_stage
        # Map stages to the file they should save to
        save_targets = {
            "ingested": "reviewed",
            "reviewed": "reviewed",
            "discovered": "reviewed",
            "enriched": "enriched",
            "highlights_done": "highlights_done",
            "generated": "highlights_done",
        }
        target = save_targets.get(stage, stage)
        try:
            _save(app.state.trip, app.state.session.stage_file(target))
        except ValueError:
            pass  # Stages like "new" or "setup" have no file
        _invalidate_discovery_if_needed(stage)

    def _invalidate_discovery_if_needed(saved_stage: str):
        """Reset stale discovery output after timeline edits in discovered state."""
        if saved_stage != "discovered":
            return

        from post_trip_summary.discovery.debug_report import vacation_blend_debug_report_path
        from post_trip_summary.discovery.serialization import vacation_blend_path

        artifact_path = vacation_blend_path(app.state.session.session_dir)
        if artifact_path.exists():
            artifact_path.unlink()
        debug_report_path = vacation_blend_debug_report_path(app.state.session.session_dir)
        if debug_report_path.exists():
            debug_report_path.unlink()
        app.state.session.current_stage = "reviewed"
        app.state.session.save()

    def _on_highlights_changed():
        """Save trip and reset stage if highlights changed after synthesis."""
        from post_trip_summary.serialization import save_trip as _save
        stage = app.state.session.current_stage
        if stage in ("highlights_done", "generated"):
            # Save to enriched so re-synthesis picks up changes
            _save(app.state.trip, app.state.session.stage_file("enriched"))
            # Reset stage so user must re-run synthesis
            app.state.session.current_stage = "enriched"
            app.state.session.save()
        else:
            _save_trip()

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
        new_name = body.get("new_name", "").strip()
        try:
            merged = merge_events(day, event_ids)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if new_name:
            merged.name = new_name
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

    @app.post("/api/toggle-highlight")
    async def toggle_highlight(request: Request):
        body = await request.json()
        event = app.state.event_index.get(body.get("event_id"))
        if not event:
            raise HTTPException(404, "Event not found")
        idx = body.get("photo_index")
        if idx is None or idx >= len(event.photos):
            raise HTTPException(400, "Invalid photo index")
        photo = event.photos[idx]
        photo.is_highlight = not photo.is_highlight
        _on_highlights_changed()
        highlighted = sum(1 for p in event.photos if p.is_kept and p.is_highlight)
        kept = sum(1 for p in event.photos if p.is_kept)
        return JSONResponse({"is_highlight": photo.is_highlight,
                           "highlighted_count": highlighted, "kept_count": kept})

    @app.post("/api/bulk-action")
    async def bulk_action(request: Request):
        body = await request.json()
        event_id = body.get("event_id")
        action = body.get("action")
        valid_actions = ("keep_all", "remove_all", "highlight_all", "highlight_none")
        if not event_id or action not in valid_actions:
            raise HTTPException(400, "event_id and action (keep_all|remove_all|highlight_all|highlight_none) required")
        event = app.state.event_index.get(event_id)
        if not event:
            raise HTTPException(404, "Event not found")
        if action in ("keep_all", "remove_all"):
            keep = action == "keep_all"
            for photo in event.photos:
                photo.is_kept = keep
        elif action == "highlight_all":
            for photo in event.photos:
                if photo.is_kept:
                    photo.is_highlight = True
        elif action == "highlight_none":
            for photo in event.photos:
                photo.is_highlight = False
        if action in ("highlight_all", "highlight_none"):
            _on_highlights_changed()
        else:
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
        if current in ("reviewed", "discovered"):
            return JSONResponse({"stage": current, "next_step": STAGE_TO_STEP[current]})
        idx = STAGES.index(current)
        if idx + 1 < len(STAGES):
            app.state.session.current_stage = STAGES[idx + 1]
            app.state.session.save()
            _save_trip()
        step = STAGE_TO_STEP.get(app.state.session.current_stage, "review")
        return JSONResponse({"stage": app.state.session.current_stage, "next_step": step})

    TYPE_ICONS = {
        "landmark": "\U0001f3db\ufe0f",
        "restaurant": "\U0001f37d\ufe0f",
        "hotel": "\U0001f3e8",
        "activity": "\U0001f3af",
        "transit": "\U0001f68c",
        "unknown": "\u2753",
    }

    @app.get("/wizard/review", response_class=HTMLResponse)
    def wizard_review():
        if app.state.trip is None:
            return RedirectResponse("/wizard/setup", status_code=307)
        ctx = _get_wizard_context(app.state.session)
        ctx["trip"] = app.state.trip
        ctx["type_icons"] = TYPE_ICONS
        template = env.get_template("review.html")
        return HTMLResponse(template.render(**ctx))

    @app.get("/wizard/discovery", response_class=HTMLResponse)
    def wizard_discovery():
        if app.state.trip is None:
            return RedirectResponse("/wizard/setup", status_code=307)

        from post_trip_summary.discovery.debug_report import (
            save_vacation_blend_debug_report,
            vacation_blend_debug_report_path,
        )
        from post_trip_summary.discovery.serialization import (
            load_vacation_blend,
            vacation_blend_path,
        )
        from post_trip_summary.discovery.service import run_discovery_for_session
        from post_trip_summary.discovery.taxonomy import VACATION_THEMES

        artifact_path = vacation_blend_path(app.state.session.session_dir)
        debug_report_path = vacation_blend_debug_report_path(app.state.session.session_dir)
        if artifact_path.exists():
            blend = load_vacation_blend(artifact_path)
            if not debug_report_path.exists():
                save_vacation_blend_debug_report(debug_report_path, blend)
        else:
            blend = run_discovery_for_session(app.state.session, advance_stage=False)

        ctx = _get_wizard_context(app.state.session)
        ctx["blend"] = blend
        ctx["themes"] = VACATION_THEMES
        ctx["theme_labels"] = {theme.id: theme.label for theme in VACATION_THEMES}
        ctx["theme_options"] = [
            {"id": theme.id, "label": theme.label, "description": theme.description}
            for theme in VACATION_THEMES
        ]
        template = env.get_template("discovery.html")
        return HTMLResponse(template.render(**ctx))

    @app.post("/api/discovery/update")
    async def discovery_update(request: Request):
        from post_trip_summary.discovery.debug_report import (
            save_vacation_blend_debug_report,
            vacation_blend_debug_report_path,
        )
        from post_trip_summary.discovery.models import ThemeScore
        from post_trip_summary.discovery.serialization import (
            load_vacation_blend,
            save_vacation_blend,
            vacation_blend_path,
        )
        from post_trip_summary.discovery.taxonomy import get_theme_label, validate_theme_ids

        try:
            body = await request.json()
        except Exception:
            raise HTTPException(400, "Malformed JSON body")
        if not isinstance(body, dict):
            raise HTTPException(400, "JSON body must be an object")

        primary_ids = body.get("primary_theme_ids", body.get("primary_themes", []))
        secondary_ids = body.get("secondary_theme_ids", body.get("secondary_themes", []))
        if not isinstance(primary_ids, list) or not isinstance(secondary_ids, list):
            raise HTTPException(400, "primary and secondary theme IDs must be lists")
        if not all(isinstance(theme_id, str) for theme_id in primary_ids + secondary_ids):
            raise HTTPException(400, "theme IDs must be strings")

        if len(primary_ids) != len(set(primary_ids)):
            raise HTTPException(400, "duplicate primary theme IDs")
        if len(secondary_ids) != len(set(secondary_ids)):
            raise HTTPException(400, "duplicate secondary theme IDs")
        overlap = sorted(set(primary_ids).intersection(secondary_ids))
        if overlap:
            raise HTTPException(400, f"theme IDs cannot be both primary and secondary: {', '.join(overlap)}")

        try:
            validate_theme_ids(primary_ids + secondary_ids)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

        artifact_path = vacation_blend_path(app.state.session.session_dir)
        if not artifact_path.exists():
            raise HTTPException(404, "Vacation blend artifact not found")

        blend = load_vacation_blend(artifact_path)
        existing_scores = {
            score.theme_id: score
            for score in [*blend.primary, *blend.secondary]
        }
        diagnostics_scores = blend.diagnostics.get("theme_scores", {})
        if not isinstance(diagnostics_scores, dict):
            diagnostics_scores = {}

        def _score_for(theme_id: str) -> ThemeScore:
            if theme_id in existing_scores:
                return existing_scores[theme_id]
            return ThemeScore(
                theme_id=theme_id,
                label=get_theme_label(theme_id),
                score=float(diagnostics_scores.get(theme_id, 0.0)),
                evidence=[],
                sample_event_ids=[],
            )

        previous_selected = {score.theme_id for score in [*blend.primary, *blend.secondary]}
        selected = set(primary_ids).union(secondary_ids)
        rejected = set(blend.rejected)
        rejected.update(previous_selected - selected)
        rejected.difference_update(selected)

        blend.primary = [_score_for(theme_id) for theme_id in primary_ids]
        blend.secondary = [_score_for(theme_id) for theme_id in secondary_ids]
        blend.rejected = sorted(rejected)
        save_vacation_blend(artifact_path, blend)
        save_vacation_blend_debug_report(
            vacation_blend_debug_report_path(app.state.session.session_dir),
            blend,
        )

        if app.state.session.current_stage == "reviewed":
            app.state.session.current_stage = "discovered"
            app.state.session.save()

        return JSONResponse({
            "stage": app.state.session.current_stage,
            "next_step": STAGE_TO_STEP.get(app.state.session.current_stage, "enrich"),
            "primary": [score.label for score in blend.primary],
            "primary_theme_ids": [score.theme_id for score in blend.primary],
        })

    @app.get("/wizard/enrich", response_class=HTMLResponse)
    def wizard_enrich():
        if app.state.trip is None:
            return RedirectResponse("/wizard/setup", status_code=307)
        if app.state.session.current_stage == "reviewed":
            return RedirectResponse("/wizard/discovery", status_code=307)
        # If already enriched, redirect forward
        if app.state.session.current_stage not in ("reviewed", "discovered", "enriched"):
            step = STAGE_TO_STEP.get(app.state.session.current_stage, "setup")
            if step not in ("enrich", "highlights", "generate"):
                return RedirectResponse(f"/wizard/{step}", status_code=307)
        ctx = _get_wizard_context(app.state.session)
        ctx["stage_title"] = "Vision Enrichment"
        template = env.get_template("enrich.html")
        return HTMLResponse(template.render(**ctx))

    @app.get("/wizard/highlights", response_class=HTMLResponse)
    def wizard_highlights():
        if app.state.trip is None:
            return RedirectResponse("/wizard/setup", status_code=307)
        ctx = _get_wizard_context(app.state.session)
        ctx["trip"] = app.state.trip
        ctx["type_icons"] = TYPE_ICONS
        template = env.get_template("highlights.html")
        return HTMLResponse(template.render(**ctx))

    # --- Generate page and API ---

    @app.get("/wizard/generate", response_class=HTMLResponse)
    def wizard_generate():
        if app.state.trip is None:
            return RedirectResponse("/wizard/setup", status_code=307)
        ctx = _get_wizard_context(app.state.session)
        ctx["output_dir"] = str(app.state.session.output_dir)
        template = env.get_template("generate.html")
        return HTMLResponse(template.render(**ctx))

    @app.post("/api/generate")
    async def api_generate(request: Request):
        if app.state.trip is None:
            raise HTTPException(400, "No trip loaded")

        body = await request.json()
        trip = app.state.trip
        session = app.state.session
        output_dir = session.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        files = []

        # Generate route map for story/PDF outputs
        map_image = _generate_static_map(trip, output_dir)

        if body.get("photo_prep"):
            from post_trip_summary.output.photo_prep import prepare_photos
            prepare_photos(trip, output_dir)
            files.append({
                "type": "photo_prep",
                "path": str(output_dir / "photos"),
            })

        if body.get("trip_story"):
            from post_trip_summary.output.trip_story import generate_trip_story
            out = output_dir / "trip-story.html"
            generate_trip_story(trip, out, map_image=map_image)
            files.append({
                "type": "trip_story",
                "path": str(out),
                "preview_url": "/story",
            })

        if body.get("detailed_record"):
            from post_trip_summary.output.detailed_record import generate_detailed_record
            out = output_dir / "detailed-record.html"
            generate_detailed_record(trip, out)
            files.append({
                "type": "detailed_record",
                "path": str(out),
                "preview_url": "/detailed",
            })

        if body.get("shareable_pdf"):
            from post_trip_summary.output.shareable_pdf import generate_shareable_pdf
            out = output_dir / "shareable-summary.pdf"
            generate_shareable_pdf(trip, out, map_image=map_image)
            files.append({
                "type": "shareable_pdf",
                "path": str(out),
                "preview_url": "/summary",
            })

        if body.get("blog_post"):
            from post_trip_summary.output.blog_post import generate_blog_post
            out = output_dir / "blog-post.html"
            generate_blog_post(trip, out)
            files.append({
                "type": "blog_post",
                "path": str(out),
                "preview_url": "/blog",
            })

        session.current_stage = "generated"
        session.save()

        return JSONResponse({
            "status": "ok",
            "files": files,
            "output_dir": str(output_dir),
        })

    # --- Output preview endpoints ---

    @app.get("/story", response_class=HTMLResponse)
    def preview_story():
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        from post_trip_summary.output.trip_story import build_story_context
        template = env.get_template("trip_story.html")
        return HTMLResponse(template.render(**build_story_context(
            app.state.trip,
            map_image=None,
        )))

    @app.get("/detailed", response_class=HTMLResponse)
    def preview_detailed():
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        template = env.get_template("detailed_record.html")
        return HTMLResponse(template.render(trip=app.state.trip))

    @app.get("/summary", response_class=HTMLResponse)
    def preview_summary():
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        from post_trip_summary.output.shareable_pdf import select_highlights, compute_stats
        template = env.get_template("shareable_summary.html")
        return HTMLResponse(template.render(
            trip=app.state.trip,
            highlights=select_highlights(app.state.trip),
            stats=compute_stats(app.state.trip),
            map_image=None,
        ))

    @app.get("/blog", response_class=HTMLResponse)
    def preview_blog():
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        from post_trip_summary.output.shareable_pdf import select_highlights
        template = env.get_template("blog_post.html")
        return HTMLResponse(template.render(
            trip=app.state.trip,
            highlights=select_highlights(app.state.trip),
        ))

    return app


def _generate_static_map(trip, output_dir) -> str | None:
    """Generate a static map image showing major stops. Returns relative path or None."""
    try:
        from staticmap import StaticMap, CircleMarker
        m = StaticMap(800, 400)
        for day in trip.days:
            for event in day.events:
                if event.location.lat and event.location.lon:
                    m.add_marker(CircleMarker((event.location.lon, event.location.lat), "#e74c3c", 8))
        if m.markers:
            map_path = output_dir / "route-map.png"
            image = m.render()
            image.save(str(map_path))
            return "route-map.png"
    except Exception:
        pass
    return None
