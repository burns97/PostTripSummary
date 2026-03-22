"""FastAPI application factory for the wizard server."""
from pathlib import Path

import jinja2
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from post_trip_summary.config import SessionConfig, STAGES
from post_trip_summary.serialization import load_trip
from post_trip_summary.settings import get_vision_settings

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

    # Placeholder routes for remaining wizard steps
    for step_name in ["ingest", "review", "enrich", "highlights", "generate"]:
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
    compiled = env.from_string(template_str)

    @app.get(f"/wizard/{step_name}", name=f"wizard_{step_name}")
    def wizard_placeholder(compiled=compiled, step_name=step_name):
        from post_trip_summary.server.app import _get_wizard_context
        ctx = _get_wizard_context(app.state.session)
        return HTMLResponse(compiled.render(**ctx))
