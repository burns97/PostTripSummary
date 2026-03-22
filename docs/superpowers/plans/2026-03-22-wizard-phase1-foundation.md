# Wizard Phase 1: Foundation + Wizard Shell + Setup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the new server package with wizard navigation and a working Setup page, so the user can `post-trip-summary start <slug>` and configure trip inputs in the browser.

**Architecture:** New `server/` package alongside existing `preview/`. FastAPI app factory holds session state. Wizard shell template with step indicator wraps all pages. Setup page is the first interactive wizard step.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, vanilla JS, uvicorn

**Spec:** `docs/superpowers/specs/2026-03-22-browser-gui-wizard-design.md`

**Phase plan:** This is Phase 1 of 5. Phases 2-5 will add progress/ingest, review, enrich/highlights, and generate/invalidation respectively.

**Prerequisites:** Install `httpx` for FastAPI test client: `pip install httpx`

---

### Task 1: Update Stage Model in config.py

**Files:**
- Modify: `src/post_trip_summary/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests for new stage model**

Add to `tests/test_config.py`:

```python
def test_new_stages_list():
    from post_trip_summary.config import STAGES
    assert STAGES == ["new", "setup", "ingested", "reviewed", "enriched", "highlights_done", "generated"]


def test_stage_file_ingested(tmp_path):
    from post_trip_summary.config import create_session
    session = create_session("test", base_dir=tmp_path)
    assert session.stage_file("ingested").name == "trip_ingested.json"


def test_stage_file_reviewed(tmp_path):
    from post_trip_summary.config import create_session
    session = create_session("test", base_dir=tmp_path)
    assert session.stage_file("reviewed").name == "trip_reviewed.json"


def test_stage_file_highlights_done(tmp_path):
    from post_trip_summary.config import create_session
    session = create_session("test", base_dir=tmp_path)
    assert session.stage_file("highlights_done").name == "trip_final.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py -v -k "new_stages or stage_file_ingested or stage_file_reviewed or stage_file_highlights"`
Expected: FAIL — old STAGES list doesn't match, stage_file() doesn't know new stage names

- [ ] **Step 3: Update STAGES and stage_file()**

In `src/post_trip_summary/config.py`, update:

```python
# Line 17 — replace STAGES
STAGES = ["new", "setup", "ingested", "reviewed", "enriched", "highlights_done", "generated"]
```

Update `stage_file()` method (lines 48-56):

```python
def stage_file(self, stage: str) -> Path:
    filenames = {
        # New wizard stages
        "ingested": "trip_ingested.json",
        "reviewed": "trip_reviewed.json",
        "enriched": "trip_enriched.json",
        "highlights_done": "trip_final.json",
        # Legacy (deprecated — kept so existing CLI commands don't crash)
        "ingest": "trip_data.json",
        "skeleton": "trip_skeleton.json",
        "skeleton_reviewed": "trip_skeleton_reviewed.json",
        "final": "trip_final.json",
    }
    if stage not in filenames:
        raise ValueError(f"No file for stage: {stage}")
    return self.session_dir / filenames[stage]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All config tests PASS

- [ ] **Step 5: Fix any other tests broken by stage rename**

Run: `python -m pytest -v`
The stage name changes will break tests in `test_config.py` that reference old stage names (like `test_current_stage_tracking`). Update those tests to use new stage names. Also update `STAGE_ORDER` in `cli.py` (line 74) and any stage string references in `cli.py` to match the new names. The old `resume` pipeline logic will be replaced in a later step, but it needs to not crash for now.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/post_trip_summary/config.py src/post_trip_summary/cli.py tests/test_config.py
git commit -m "Update stage model for wizard flow"
```

---

### Task 2: Create Server Package with App Factory

**Files:**
- Create: `src/post_trip_summary/server/__init__.py`
- Create: `src/post_trip_summary/server/app.py`
- Create: `src/post_trip_summary/server/routes/__init__.py`
- Test: `tests/test_server_app.py`

- [ ] **Step 1: Write failing test for app factory**

Create `tests/test_server_app.py`:

```python
from pathlib import Path
from fastapi.testclient import TestClient
from post_trip_summary.config import create_session


def test_create_app_returns_fastapi(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    assert app is not None
    client = TestClient(app)
    response = client.get("/api/stage/current")
    assert response.status_code == 200
    assert response.json()["stage"] == "new"


def test_app_state_holds_session(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    assert app.state.session.slug == "test-trip"
    assert app.state.trip is None  # No trip data at "new" stage
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server_app.py -v`
Expected: FAIL — `post_trip_summary.server` does not exist

- [ ] **Step 3: Create server package and app factory**

Create `src/post_trip_summary/server/__init__.py`:

```python
```

Create `src/post_trip_summary/server/routes/__init__.py`:

```python
```

Create `src/post_trip_summary/server/app.py`:

```python
"""FastAPI application factory for the wizard server."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from post_trip_summary.config import SessionConfig
from post_trip_summary.serialization import load_trip


def _load_trip_for_stage(session: SessionConfig):
    """Load the most recent trip data based on current stage, or None."""
    from post_trip_summary.config import STAGES
    # Walk backward from current stage to find the most recent stage file
    stage_idx = STAGES.index(session.current_stage)
    for i in range(stage_idx, -1, -1):
        stage = STAGES[i]
        try:
            path = session.stage_file(stage)
            if path.exists():
                return load_trip(path)
        except ValueError:
            continue  # Stages like "new" and "setup" have no file
    return None


def create_app(session: SessionConfig) -> FastAPI:
    """Create the wizard FastAPI app for a session."""
    app = FastAPI(title="Post-Trip Summary Wizard")

    app.state.session = session
    app.state.trip = _load_trip_for_stage(session)
    app.state.thumb_cache = {}
    app.state.background_task = None

    @app.get("/api/stage/current")
    def get_current_stage():
        return JSONResponse({
            "stage": app.state.session.current_stage,
            "name": app.state.session.name,
            "slug": app.state.session.slug,
        })

    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_server_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/server/ tests/test_server_app.py
git commit -m "Add server package with app factory and stage endpoint"
```

---

### Task 3: Wizard Shell Template with Step Indicator

**Files:**
- Create: `src/post_trip_summary/templates/wizard.html`
- Modify: `src/post_trip_summary/server/app.py` (add Jinja2 setup and root route)
- Test: `tests/test_server_app.py` (extend)

- [ ] **Step 1: Write failing test for wizard root route**

Add to `tests/test_server_app.py`:

```python
def test_wizard_root_redirects_to_current_step(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    # "new" stage should redirect to setup
    assert "/wizard/setup" in response.headers["location"]


def test_wizard_setup_page_renders(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.get("/wizard/setup")
    assert response.status_code == 200
    assert "Setup" in response.text
    assert "test-trip" in response.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_server_app.py -v -k "wizard"`
Expected: FAIL — routes don't exist

- [ ] **Step 3: Create wizard.html base template**

Create `src/post_trip_summary/templates/wizard.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ session.name }} — {% block title %}Wizard{% endblock %}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #1a1a2e; color: #eee; }

  /* Step indicator */
  .wizard-steps { display: flex; align-items: center; justify-content: center; gap: 0; padding: 1rem 2rem; background: #16213e; border-bottom: 1px solid #333; }
  .step { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; font-size: 0.85rem; color: #666; text-decoration: none; cursor: default; }
  .step.completed { color: #2ecc71; cursor: pointer; }
  .step.completed:hover { text-decoration: underline; }
  .step.current { color: #fff; font-weight: 600; }
  .step.locked { color: #444; }
  .step-number { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; font-size: 0.75rem; border: 2px solid currentColor; }
  .step.completed .step-number { background: #2ecc71; border-color: #2ecc71; color: #000; }
  .step.current .step-number { border-color: #fff; }
  .step-arrow { color: #444; margin: 0 0.25rem; }

  /* Content area */
  .wizard-content { max-width: 1400px; margin: 0 auto; padding: 1.5rem 2rem; }
  h2 { margin-bottom: 1rem; font-size: 1.4rem; }

  /* Common form elements */
  .form-group { margin-bottom: 1rem; }
  .form-group label { display: block; margin-bottom: 0.25rem; font-size: 0.85rem; color: #aaa; }
  .form-group input[type="text"] { width: 100%; padding: 0.5rem; background: #0f3460; border: 1px solid #333; color: #eee; border-radius: 4px; font-size: 0.9rem; }
  .form-group input[type="text"]:focus { outline: none; border-color: #5dade2; }
  .form-group .hint { font-size: 0.75rem; color: #666; margin-top: 0.25rem; }
  .form-group .error { font-size: 0.75rem; color: #e74c3c; margin-top: 0.25rem; }
  .form-group .success { font-size: 0.75rem; color: #2ecc71; margin-top: 0.25rem; }

  .btn { padding: 0.6rem 1.2rem; border: none; border-radius: 4px; font-size: 0.9rem; cursor: pointer; }
  .btn-primary { background: #2ecc71; color: #000; font-weight: 600; }
  .btn-primary:hover { background: #27ae60; }
  .btn-primary:disabled { background: #555; color: #888; cursor: not-allowed; }
  .btn-secondary { background: #0f3460; color: #ddd; border: 1px solid #555; }
  .btn-secondary:hover { background: #1a4a8a; }

  {% block extra_css %}{% endblock %}
</style>
</head>
<body>
  <nav class="wizard-steps">
    {% set steps = [
      ("setup", "Setup"),
      ("ingest", "Ingest"),
      ("review", "Review"),
      ("enrich", "Enrich"),
      ("highlights", "Highlights"),
      ("generate", "Generate"),
    ] %}
    {% for step_id, step_label in steps %}
      {% if not loop.first %}<span class="step-arrow">&rarr;</span>{% endif %}
      {% if step_id in completed_steps %}
        <a href="/wizard/{{ step_id }}" class="step completed">
          <span class="step-number">&#10003;</span> {{ step_label }}
        </a>
      {% elif step_id == current_step %}
        <span class="step current">
          <span class="step-number">{{ loop.index }}</span> {{ step_label }}
        </span>
      {% else %}
        <span class="step locked">
          <span class="step-number">{{ loop.index }}</span> {{ step_label }}
        </span>
      {% endif %}
    {% endfor %}
  </nav>

  <div class="wizard-content">
    {% block content %}{% endblock %}
  </div>

  {% block extra_js %}{% endblock %}
</body>
</html>
```

- [ ] **Step 4: Create setup.html template**

Create `src/post_trip_summary/templates/setup.html`:

```html
{% extends "wizard.html" %}
{% block title %}Setup{% endblock %}

{% block content %}
<h2>Trip Setup</h2>
<p style="color: #aaa; margin-bottom: 1.5rem;">Configure your data sources before processing.</p>

<form id="setup-form">
  <div class="form-group">
    <label>Trip Name</label>
    <input type="text" value="{{ session.name }}" disabled>
  </div>

  <div class="form-group">
    <label>Photos Directory <span style="color: #e74c3c;">*</span></label>
    <input type="text" name="photos" id="input-photos" value="{{ inputs.get('photos', '') }}" placeholder="e.g., D:\Vacation\Photos">
    <div class="hint">Required. Path to the folder containing your trip photos.</div>
  </div>

  <div class="form-group">
    <label>Excel Itinerary</label>
    <input type="text" name="excel" id="input-excel" value="{{ inputs.get('excel', '') }}" placeholder="e.g., D:\Vacation\itinerary.xlsx">
    <div class="hint">Optional. Tabs: Accommodations, Transit, Activities, Expenses.</div>
  </div>

  <div class="form-group">
    <label>Credit Card CSV</label>
    <input type="text" name="credit_card" id="input-credit_card" value="{{ inputs.get('credit_card', '') }}" placeholder="Optional">
  </div>

  <div class="form-group">
    <label>Google Maps Timeline JSON</label>
    <input type="text" name="google_maps" id="input-google_maps" value="{{ inputs.get('google_maps', '') }}" placeholder="Optional">
  </div>

  <div class="form-group">
    <label>Apple Health Export XML</label>
    <input type="text" name="apple_health" id="input-apple_health" value="{{ inputs.get('apple_health', '') }}" placeholder="Optional">
  </div>

  <div class="form-group">
    <label>Day One Journal JSON</label>
    <input type="text" name="dayone" id="input-dayone" value="{{ inputs.get('dayone', '') }}" placeholder="Optional">
  </div>

  <hr style="border-color: #333; margin: 1.5rem 0;">

  <h3 style="margin-bottom: 1rem;">Vision Provider</h3>

  <div class="form-group">
    <label>Provider</label>
    <select name="vision_provider" id="vision-provider" style="padding: 0.5rem; background: #0f3460; border: 1px solid #333; color: #eee; border-radius: 4px;">
      <option value="gemini" {{ 'selected' if vision.provider == 'gemini' }}>Gemini</option>
      <option value="claude" {{ 'selected' if vision.provider == 'claude' }}>Claude</option>
    </select>
  </div>

  <div class="form-group">
    <label>API Key Status</label>
    <span style="color: {{ '#2ecc71' if vision.has_key else '#e74c3c' }};">
      {{ 'Configured' if vision.has_key else 'Not configured — set in environment or settings.toml' }}
    </span>
  </div>

  <div style="margin-top: 2rem; display: flex; justify-content: flex-end;">
    <button type="submit" class="btn btn-primary" id="start-btn">Start Processing</button>
  </div>
</form>

<div id="status-message" style="margin-top: 1rem; display: none;"></div>
{% endblock %}

{% block extra_js %}
<script>
document.getElementById("setup-form").addEventListener("submit", async function(e) {
  e.preventDefault();
  const btn = document.getElementById("start-btn");
  const status = document.getElementById("status-message");
  btn.disabled = true;
  btn.textContent = "Saving...";
  status.style.display = "none";

  const inputs = {};
  for (const name of ["photos", "excel", "credit_card", "google_maps", "apple_health", "dayone"]) {
    const val = document.getElementById("input-" + name).value.trim();
    if (val) inputs[name] = val;
  }

  const settings = { vision_provider: document.getElementById("vision-provider").value };

  try {
    const resp = await fetch("/api/session/inputs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inputs, settings }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      status.style.display = "block";
      status.innerHTML = '<span class="error">' + (data.detail || "Validation failed") + '</span>';
      btn.disabled = false;
      btn.textContent = "Start Processing";
      return;
    }
    // Advance to ingest — for now, just show success since progress page is Phase 2
    window.location.href = "/wizard/ingest";
  } catch (err) {
    status.style.display = "block";
    status.innerHTML = '<span class="error">Network error: ' + err.message + '</span>';
    btn.disabled = false;
    btn.textContent = "Start Processing";
  }
});
</script>
{% endblock %}
```

- [ ] **Step 5: Add Jinja2 setup, wizard routes, and stage-to-step mapping to app.py**

Update `src/post_trip_summary/server/app.py` — add Jinja2 environment, wizard step helpers, root redirect, and setup page route. The key additions:

```python
import jinja2
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from post_trip_summary.config import SessionConfig, STAGES
from post_trip_summary.serialization import load_trip
from post_trip_summary.settings import get_vision_settings


# Map stages to the wizard step the user should be on next
STAGE_TO_STEP = {
    "new": "setup", "setup": "setup",
    "ingested": "review",       # ingest done → review next
    "reviewed": "enrich",       # review done → enrich next
    "enriched": "highlights",   # enrich done → highlights next
    "highlights_done": "generate",
    "generated": "generate",    # all done, stay on generate
}

# Ordered wizard steps
WIZARD_STEPS = ["setup", "ingest", "review", "enrich", "highlights", "generate"]

# Map wizard steps to the stage required to have completed that step
STEP_COMPLETED_AT = {
    "setup": "ingested",   # setup is "done" once ingest has run
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
```

Add to `create_app()`:

```python
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("post_trip_summary", "templates"),
        autoescape=True,
    )

    @app.get("/")
    def root():
        step = STAGE_TO_STEP.get(session.current_stage, "setup")
        return RedirectResponse(f"/wizard/{step}", status_code=307)

    @app.get("/wizard/setup", response_class=HTMLResponse)
    def wizard_setup():
        ctx = _get_wizard_context(app.state.session)
        vs = get_vision_settings()
        # Session-level provider overrides global setting
        provider = app.state.session.settings.get("vision_provider", vs.get("provider", "gemini"))
        ctx["inputs"] = app.state.session.inputs
        ctx["vision"] = {
            "provider": provider,
            "has_key": bool(vs.get("api_key")),
        }
        template = env.get_template("setup.html")
        return template.render(**ctx)

    # Placeholder routes for other wizard steps (return simple page for now)
    for step_name in ["ingest", "review", "enrich", "highlights", "generate"]:
        _add_placeholder_route(app, env, step_name)
```

Add the placeholder helper (outside `create_app`):

```python
def _add_placeholder_route(app, env, step_name):
    @app.get(f"/wizard/{step_name}", response_class=HTMLResponse, name=f"wizard_{step_name}")
    def wizard_placeholder(request: Request, _step=step_name):
        # Minimal page using wizard.html base
        html = f"""
        {{% extends "wizard.html" %}}
        {{% block title %}}{_step.title()}{{% endblock %}}
        {{% block content %}}<h2>{_step.title()}</h2><p style="color:#888;">Coming soon (Phase 2+).</p>{{% endblock %}}
        """
        template = env.from_string(html)
        ctx = _get_wizard_context(app.state.session)
        return template.render(**ctx)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_server_app.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/post_trip_summary/server/ src/post_trip_summary/templates/wizard.html src/post_trip_summary/templates/setup.html tests/test_server_app.py
git commit -m "Add wizard shell template with step indicator and setup page"
```

---

### Task 4: Session Input Management API

**Files:**
- Modify: `src/post_trip_summary/server/app.py`
- Test: `tests/test_server_app.py`

- [ ] **Step 1: Write failing tests for input API**

Add to `tests/test_server_app.py`:

```python
def test_update_inputs_saves_to_session(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)

    # Create a fake photos directory
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    response = client.post("/api/session/inputs", json={
        "inputs": {"photos": str(photos_dir)},
        "settings": {},
    })
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # Verify session was updated
    assert app.state.session.inputs["photos"] == str(photos_dir)
    assert app.state.session.current_stage == "setup"


def test_update_inputs_validates_photos_path(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)

    response = client.post("/api/session/inputs", json={
        "inputs": {"photos": "/nonexistent/path"},
        "settings": {},
    })
    assert response.status_code == 422


def test_update_inputs_optional_sources_not_validated_if_empty(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)

    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    response = client.post("/api/session/inputs", json={
        "inputs": {"photos": str(photos_dir)},
        "settings": {"vision_provider": "gemini"},
    })
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_server_app.py -v -k "update_inputs"`
Expected: FAIL — endpoint doesn't exist

- [ ] **Step 3: Implement the inputs API endpoint**

Add to `create_app()` in `src/post_trip_summary/server/app.py` (ensure `Request` is imported from `fastapi` at the top of the file):

```python
    @app.post("/api/session/inputs")
    async def update_session_inputs(request: Request):
        request_body = await request.json()
        inputs = request_body.get("inputs", {})
        settings = request_body.get("settings", {})

        # Validate photos path exists if provided
        photos_path = inputs.get("photos", "")
        if photos_path:
            from pathlib import Path
            if not Path(photos_path).is_dir():
                from fastapi import HTTPException
                raise HTTPException(422, f"Photos directory not found: {photos_path}")

        # Validate optional source paths exist if provided
        for key in ["excel", "credit_card", "google_maps", "apple_health", "dayone"]:
            path = inputs.get(key, "")
            if path:
                from pathlib import Path
                if not Path(path).exists():
                    from fastapi import HTTPException
                    raise HTTPException(422, f"File not found: {path}")

        # Update session
        app.state.session.inputs.update(inputs)
        if "vision_provider" in settings:
            app.state.session.settings["vision_provider"] = settings["vision_provider"]

        # Advance stage to setup if still at new
        if app.state.session.current_stage == "new":
            app.state.session.current_stage = "setup"

        app.state.session.save()
        return JSONResponse({"status": "ok"})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_server_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/server/app.py tests/test_server_app.py
git commit -m "Add session input management API endpoint"
```

---

### Task 5: CLI `start` Command

**Files:**
- Modify: `src/post_trip_summary/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for `start` command**

Add to `tests/test_cli.py`:

```python
def test_start_command_exists():
    from click.testing import CliRunner
    from post_trip_summary.cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, ["start", "--help"])
    assert result.exit_code == 0
    assert "Launch the browser wizard" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v -k "start_command"`
Expected: FAIL — no such command

- [ ] **Step 3: Add `start` command to cli.py**

Add the `start` command after the existing commands in `src/post_trip_summary/cli.py`:

```python
@cli.command()
@click.argument("slug")
@click.option("--port", default=8765, help="Server port")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def start(slug: str, port: int, base_dir: Path | None):
    """Launch the browser wizard for a trip session."""
    import webbrowser
    import uvicorn
    from post_trip_summary.config import load_session, STAGES

    session = load_session(slug, base_dir=base_dir)

    # Check for old-format sessions
    old_stages = {"ingest", "skeleton", "skeleton_reviewed", "final"}
    if session.current_stage in old_stages:
        click.echo(f"Session '{slug}' uses an old stage format ('{session.current_stage}').")
        click.echo("Please delete and recreate this session:")
        click.echo(f"  post-trip-summary delete {slug}")
        click.echo(f"  post-trip-summary new \"{session.name}\"")
        raise SystemExit(1)

    from post_trip_summary.server.app import create_app
    app = create_app(session)

    click.echo(f"\nStarting wizard for '{session.name}' at http://localhost:{port}")
    click.echo("Press Ctrl+C to stop the server.\n")
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
```

- [ ] **Step 4: Make `resume` an alias for `start`**

Update the existing `resume` command to delegate to `start`. Replace the `resume` function body with:

```python
@cli.command()
@click.argument("slug")
@click.option("--port", default=8765, help="Server port")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def resume(slug: str, port: int, base_dir: Path | None):
    """Resume a trip session in the browser wizard (alias for start)."""
    ctx = click.get_current_context()
    ctx.invoke(start, slug=slug, port=port, base_dir=base_dir)
```

Note: The old `resume` command with its full pipeline logic should be kept in the file but renamed to `_legacy_resume` (or similar, as a regular function, not a Click command) for reference during later phases. It will be deleted when all wizard phases are complete.

- [ ] **Step 5: Simplify the `new` command**

Update the `new` command (lines 29-48) to remove `--photos`, `--excel`, and the interactive prompt. It should just create the session:

```python
@cli.command()
@click.argument("name")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def new(name: str, base_dir: Path | None):
    """Create a new trip session."""
    session = create_session(name, base_dir=base_dir)
    session.save()
    click.echo(f"Created session: {session.slug}")
    click.echo(f"Run: post-trip-summary start {session.slug}")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (some old tests for `new` command behavior may need updating since `--photos` is removed)

- [ ] **Step 7: Run full test suite and fix broken CLI tests**

Run: `python -m pytest -v`

The following tests in `tests/test_cli.py` will break because `new` no longer accepts `--photos` or interactive prompts:
- `test_new_command` — remove the `input="/fake/photos\n"` parameter and `--photos` assertions. Just assert the session slug is printed.
- `test_list_command_with_sessions` — update session creation to not pass photos input.
- `test_delete_command` — same as above.

The `test_cli_pipeline.py` tests reference the old `resume` command behavior. Update `test_resume_unknown_session` to test the new `start` command instead:
```python
def test_start_unknown_session():
    result = runner.invoke(cli, ["start", "nonexistent", "--base-dir", str(tmp_path)])
    assert result.exit_code != 0
```

Expected: All tests PASS after fixes.

- [ ] **Step 8: Commit**

```bash
git add src/post_trip_summary/cli.py tests/test_cli.py
git commit -m "Add CLI start command and simplify new command for wizard flow"
```

---

### Task 6: Photo Serving Routes

**Files:**
- Modify: `src/post_trip_summary/server/app.py`
- Test: `tests/test_server_app.py`

The wizard pages will need photo serving for the review and highlights steps. Migrate the photo serving logic from `preview/server.py` now so it's available.

- [ ] **Step 1: Write failing test for photo serving**

Add to `tests/test_server_app.py`:

```python
from datetime import datetime, date
from post_trip_summary.models import Trip, Day, Event, Photo, Location
from PIL import Image
import io


def _make_test_trip(tmp_path):
    """Create a minimal trip with one photo on disk."""
    img_path = tmp_path / "photo.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img_path, "JPEG")

    photo = Photo(path=img_path, timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294))
    event = Event(
        id="day01-event01", type="landmark", name="Test",
        time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
        location=Location(lat=48.858, lon=2.294, name="Test", address=None, city="Paris", country="France"),
        photos=[photo],
    )
    return Trip(
        name="Test", date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )


def test_photo_serving_by_event_and_index(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    # Rebuild event index since trip was set after creation
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)

    client = TestClient(app)
    response = client.get("/photos/day01-event01/0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server_app.py -v -k "photo_serving"`
Expected: FAIL — route and function don't exist

- [ ] **Step 3: Add photo serving and thumbnail logic to app.py**

Add to `src/post_trip_summary/server/app.py`, outside `create_app()`:

```python
from pathlib import Path as FilePath

THUMB_MAX_WIDTH = 300


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
    import io
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
```

Add inside `create_app()`:

```python
    app.state.event_index = _build_event_index(app.state.trip)

    @app.get("/photos/{event_id}/{photo_idx}")
    def serve_photo_by_event(event_id: str, photo_idx: int):
        from fastapi.responses import Response
        event = app.state.event_index.get(event_id)
        if not event or photo_idx >= len(event.photos):
            from fastapi import HTTPException
            raise HTTPException(404, "Photo not found")
        photo = event.photos[photo_idx]
        cache_key = (event_id, photo_idx)
        if cache_key not in app.state.thumb_cache:
            app.state.thumb_cache[cache_key] = _make_thumbnail(photo.path)
        return Response(content=app.state.thumb_cache[cache_key], media_type="image/jpeg")

    @app.get("/photos/{filename}")
    def serve_photo_by_name(filename: str):
        """Serve photo by filename stem (for output preview templates)."""
        from fastapi.responses import Response
        from fastapi import HTTPException
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_server_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/server/app.py tests/test_server_app.py
git commit -m "Add photo serving routes with thumbnail caching to wizard server"
```

---

### Task 7: Integration Test — End-to-End Setup Flow

**Files:**
- Test: `tests/test_wizard_integration.py`

- [ ] **Step 1: Write integration test for the full setup flow**

Create `tests/test_wizard_integration.py`:

```python
"""Integration test: create session via CLI, launch wizard, configure inputs."""
from pathlib import Path
from click.testing import CliRunner
from fastapi.testclient import TestClient
from post_trip_summary.cli import cli
from post_trip_summary.config import load_session


def test_new_then_start_setup_flow(tmp_path):
    """Simulate: new -> start -> configure inputs on setup page."""
    runner = CliRunner()

    # 1. Create session
    result = runner.invoke(cli, ["new", "Test Trip", "--base-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "test-trip" in result.output

    # 2. Load session and create app (simulates what `start` does)
    session = load_session("test-trip", base_dir=tmp_path)
    assert session.current_stage == "new"

    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)

    # 3. Root redirects to setup
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert "/wizard/setup" in response.headers["location"]

    # 4. Setup page renders
    response = client.get("/wizard/setup")
    assert response.status_code == 200
    assert "Test Trip" in response.text

    # 5. Submit inputs
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    response = client.post("/api/session/inputs", json={
        "inputs": {"photos": str(photos_dir)},
        "settings": {"vision_provider": "gemini"},
    })
    assert response.status_code == 200

    # 6. Session updated
    assert session.current_stage == "setup"
    assert session.inputs["photos"] == str(photos_dir)

    # 7. Stage endpoint reflects current state
    response = client.get("/api/stage/current")
    assert response.json()["stage"] == "setup"
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/test_wizard_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_wizard_integration.py
git commit -m "Add integration test for wizard setup flow"
```

---

## Verification

After all tasks are complete:

1. `python -m pytest -v` — all tests pass
2. Manual test:
   ```
   post-trip-summary new "Japan 2026"
   post-trip-summary start japan-2026
   ```
   - Browser opens at `http://localhost:8765/`
   - Redirects to `/wizard/setup`
   - Step indicator shows "Setup" as current, all others locked
   - Fill in photos path, click "Start Processing"
   - Navigates to `/wizard/ingest` (placeholder page for now)
3. Ctrl+C stops the server cleanly

## What's Next (Phase 2)

Phase 2 will add:
- Thread-safe progress infrastructure (progress object, SSE endpoint)
- Progress callbacks in pipeline functions (ingest_photos, build_skeleton)
- Progress page template with live SSE updates
- "Start Processing" on Setup actually triggers ingest and shows progress
