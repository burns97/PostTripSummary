# Wizard Phase 2: Progress Infrastructure + Ingest

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the "Start Processing" button on the Setup page trigger ingest + skeleton building in a background thread, with live progress streamed to the browser via SSE. When done, auto-transition to the Review step.

**Architecture:** Thread-safe progress tracker shared between pipeline thread and SSE endpoint. Pipeline functions gain an optional `progress_callback` parameter. The ingest + skeleton build run as one compute phase, reporting sub-phase progress (scanning, scoring, geocoding, etc.).

**Tech Stack:** Python 3.10+, FastAPI, SSE (via `sse-starlette`), `asyncio.to_thread()`, threading

**Spec:** `docs/superpowers/specs/2026-03-22-browser-gui-wizard-design.md`

**Phase plan:** This is Phase 2 of 5. Phase 1 (foundation) is complete. Phase 3 will add the Review page.

**Prerequisites:** `pip install sse-starlette`

---

### Task 1: Progress Tracker

**Files:**
- Create: `src/post_trip_summary/server/progress.py`
- Test: `tests/test_progress.py`

A thread-safe progress tracker that pipeline functions write to and the SSE endpoint reads from.

- [ ] **Step 1: Write failing tests**

Create `tests/test_progress.py`:

```python
from post_trip_summary.server.progress import ProgressTracker


def test_initial_state():
    tracker = ProgressTracker()
    state = tracker.get_state()
    assert state["phase"] == ""
    assert state["current"] == 0
    assert state["total"] == 0
    assert state["label"] == ""
    assert state["done"] is False


def test_update_and_read():
    tracker = ProgressTracker()
    tracker.update("photos", 5, 100, "IMG_001.jpg")
    state = tracker.get_state()
    assert state["phase"] == "photos"
    assert state["current"] == 5
    assert state["total"] == 100
    assert state["label"] == "IMG_001.jpg"


def test_complete():
    tracker = ProgressTracker()
    tracker.complete("review")
    state = tracker.get_state()
    assert state["done"] is True
    assert state["next_stage"] == "review"


def test_fail():
    tracker = ProgressTracker()
    tracker.fail("Something went wrong")
    state = tracker.get_state()
    assert state["failed"] is True
    assert state["error"] == "Something went wrong"


def test_callback():
    tracker = ProgressTracker()
    cb = tracker.callback()
    cb("scoring", 3, 50, "photo3.jpg")
    state = tracker.get_state()
    assert state["phase"] == "scoring"
    assert state["current"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_progress.py -v`

- [ ] **Step 3: Implement ProgressTracker**

Create `src/post_trip_summary/server/progress.py`:

```python
"""Thread-safe progress tracker for compute stages."""
import threading


class ProgressTracker:
    """Shared state between pipeline thread and SSE endpoint."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            "phase": "",
            "current": 0,
            "total": 0,
            "label": "",
            "done": False,
            "failed": False,
            "error": "",
            "next_stage": "",
        }

    def update(self, phase: str, current: int, total: int, label: str = ""):
        with self._lock:
            self._state["phase"] = phase
            self._state["current"] = current
            self._state["total"] = total
            self._state["label"] = label

    def complete(self, next_stage: str):
        with self._lock:
            self._state["done"] = True
            self._state["next_stage"] = next_stage

    def fail(self, error: str):
        with self._lock:
            self._state["failed"] = True
            self._state["error"] = error

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def callback(self):
        """Return a callback function for pipeline code to call."""
        def _cb(phase: str, current: int, total: int, label: str = ""):
            self.update(phase, current, total, label)
        return _cb
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_progress.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/server/progress.py tests/test_progress.py
git commit -m "Add thread-safe progress tracker for compute stages"
```

---

### Task 2: SSE Endpoint and Compute Stage Trigger

**Files:**
- Modify: `src/post_trip_summary/server/app.py`
- Test: `tests/test_server_app.py`

Add the SSE progress endpoint and a POST endpoint to trigger compute stages.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_server_app.py`:

```python
def test_start_ingest_returns_ok(tmp_path):
    """POST /api/stage/start triggers ingest (mocked)."""
    session = create_session("test-trip", base_dir=tmp_path)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    session.inputs["photos"] = str(photos_dir)
    session.current_stage = "setup"
    session.save()

    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)

    response = client.post("/api/stage/start", json={"stage": "ingest"})
    assert response.status_code == 200
    assert response.json()["status"] == "started"


def test_progress_endpoint_exists(tmp_path):
    """GET /api/progress returns SSE stream."""
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)

    # Without a running task, should return current state
    response = client.get("/api/progress")
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_server_app.py -v -k "start_ingest or progress_endpoint"`

- [ ] **Step 3: Implement SSE and compute trigger endpoints**

Add to `src/post_trip_summary/server/app.py`:

At top level, add imports:
```python
import asyncio
import json as json_mod
from sse_starlette.sse import EventSourceResponse
from post_trip_summary.server.progress import ProgressTracker
```

Inside `create_app()`, add:

```python
    @app.post("/api/stage/start")
    async def start_stage(request: Request):
        body = await request.json()
        stage = body.get("stage")

        if app.state.background_task is not None:
            from fastapi import HTTPException
            raise HTTPException(409, "A compute stage is already running")

        if stage == "ingest":
            tracker = ProgressTracker()
            app.state.progress = tracker

            async def run_ingest():
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

            app.state.background_task = asyncio.create_task(run_ingest())
            return JSONResponse({"status": "started"})

        from fastapi import HTTPException
        raise HTTPException(400, f"Unknown stage: {stage}")

    @app.get("/api/progress")
    async def progress_stream(request: Request):
        tracker = getattr(app.state, "progress", None)

        async def event_generator():
            while True:
                if tracker is None:
                    yield {"event": "state", "data": json_mod.dumps({"done": True, "phase": "idle"})}
                    return
                state = tracker.get_state()
                yield {"event": "state", "data": json_mod.dumps(state)}
                if state.get("done") or state.get("failed"):
                    return
                await asyncio.sleep(0.5)

        return EventSourceResponse(event_generator())
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_server_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/server/app.py tests/test_server_app.py
git commit -m "Add SSE progress endpoint and compute stage trigger"
```

---

### Task 3: Ingest Pipeline Wrapper with Progress Callbacks

**Files:**
- Create: `src/post_trip_summary/server/compute.py`
- Modify: `src/post_trip_summary/pipeline/ingest/photos.py`
- Modify: `src/post_trip_summary/pipeline/quality.py`
- Modify: `src/post_trip_summary/pipeline/skeleton.py`
- Test: `tests/test_compute.py`

This task adds progress callbacks to the pipeline functions and creates the `run_ingest_pipeline` function that the server calls.

- [ ] **Step 1: Add progress_callback to ingest_photos**

In `src/post_trip_summary/pipeline/ingest/photos.py`, modify `ingest_photos()` (line 113):

Change from:
```python
def ingest_photos(directory: Path) -> list[Photo]:
```
To:
```python
def ingest_photos(directory: Path, progress_callback=None) -> list[Photo]:
```

Replace the list comprehension on line 124:
```python
photos = [extract_photo_metadata(p) for p in paths]
```
With an explicit loop:
```python
    photos = []
    for i, p in enumerate(paths):
        photos.append(extract_photo_metadata(p))
        if progress_callback:
            progress_callback("scanning", i + 1, len(paths), p.name)
```

- [ ] **Step 2: Add progress_callback to score_photos**

In `src/post_trip_summary/pipeline/quality.py`, modify `score_photos()` (line 56):

Change from:
```python
def score_photos(photos: list[Photo], thumbnail_size: int = 512) -> None:
```
To:
```python
def score_photos(photos: list[Photo], thumbnail_size: int = 512, progress_callback=None) -> None:
```

Inside the main loop (line 66), add progress reporting:
```python
    for i, photo in enumerate(photos):
        if progress_callback:
            progress_callback("scoring", i + 1, len(photos), photo.path.name)
        try:
            # ... existing scoring logic ...
```

- [ ] **Step 3: Add progress_callback to build_skeleton**

In `src/post_trip_summary/pipeline/skeleton.py`, modify `build_skeleton()` (line 115):

Change from:
```python
def build_skeleton(trip_data: dict, gap_minutes: int = 15, distance_meters: int = 200) -> Trip:
```
To:
```python
def build_skeleton(trip_data: dict, gap_minutes: int = 15, distance_meters: int = 200, progress_callback=None) -> Trip:
```

Inside the main cluster loop (line 158), add progress:
```python
    for idx, cluster in enumerate(clusters):
        if progress_callback:
            progress_callback("skeleton", idx + 1, len(clusters), f"Cluster {idx + 1}")
        # ... existing logic ...
```

- [ ] **Step 4: Run existing tests to ensure backward compatibility**

Run: `python -m pytest tests/test_ingest_photos.py tests/test_quality.py tests/test_skeleton.py -v`
Expected: All PASS (progress_callback defaults to None, no behavior change)

- [ ] **Step 5: Create run_ingest_pipeline wrapper**

Create `src/post_trip_summary/server/compute.py`:

```python
"""Compute stage runners for the wizard server."""
from pathlib import Path

from post_trip_summary.config import SessionConfig
from post_trip_summary.serialization import save_trip


def run_ingest_pipeline(session: SessionConfig, progress_callback=None) -> "Trip":
    """Run the full ingest + skeleton pipeline with progress reporting.

    This is called from a background thread via asyncio.to_thread().
    """
    trip_data = _run_ingest(session, progress_callback)
    trip = _run_skeleton(session, trip_data, progress_callback)

    # Save the ingested trip
    save_trip(trip, session.stage_file("ingested"))

    # Also save raw trip_data for debugging
    import json
    from post_trip_summary.serialization import encode_value
    raw_path = session.session_dir / "trip_data.json"
    raw_path.write_text(json.dumps(trip_data, default=encode_value, indent=2))

    return trip


def _run_ingest(session: SessionConfig, progress_callback=None) -> dict:
    """Ingest all configured data sources."""
    trip_data = {
        "photos": [], "accommodations": [], "transits": [],
        "activities": [], "expenses": [],
        "google_maps": {}, "apple_health": [], "dayone": [],
    }

    inputs = session.inputs

    # Photos (required)
    photos_path = inputs.get("photos")
    if photos_path:
        from post_trip_summary.pipeline.ingest.photos import ingest_photos
        trip_data["photos"] = ingest_photos(Path(photos_path), progress_callback=progress_callback)

    # Excel itinerary
    excel_path = inputs.get("excel")
    if excel_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing Excel itinerary...")
        from post_trip_summary.pipeline.ingest.excel import ingest_excel
        excel_data = ingest_excel(Path(excel_path))
        trip_data["accommodations"] = excel_data.get("accommodations", [])
        trip_data["transits"] = excel_data.get("transits", [])
        trip_data["activities"] = excel_data.get("activities", [])
        trip_data["expenses"].extend(excel_data.get("expenses", []))

    # Credit card CSV
    cc_path = inputs.get("credit_card")
    if cc_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing credit card CSV...")
        from post_trip_summary.pipeline.ingest.credit_card import ingest_credit_card
        trip_data["expenses"].extend(ingest_credit_card(Path(cc_path)))

    # Google Maps
    maps_path = inputs.get("google_maps")
    if maps_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing Google Maps timeline...")
        from post_trip_summary.pipeline.ingest.google_maps import ingest_google_maps
        trip_data["google_maps"] = ingest_google_maps(Path(maps_path))

    # Apple Health
    health_path = inputs.get("apple_health")
    if health_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing Apple Health data...")
        from post_trip_summary.pipeline.ingest.apple_health import ingest_apple_health
        trip_data["apple_health"] = ingest_apple_health(Path(health_path))

    # Day One
    dayone_path = inputs.get("dayone")
    if dayone_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing Day One journal...")
        from post_trip_summary.pipeline.ingest.dayone import ingest_dayone
        trip_data["dayone"] = ingest_dayone(Path(dayone_path))

    # Quality scoring
    if trip_data["photos"]:
        from post_trip_summary.pipeline.quality import score_photos, apply_quality_cull
        score_photos(trip_data["photos"], progress_callback=progress_callback)
        cull_pct = session.settings.get("quality_cull_percentile", 15)
        culled = apply_quality_cull(trip_data["photos"], percentile=cull_pct)
        if progress_callback:
            progress_callback("scoring", len(trip_data["photos"]), len(trip_data["photos"]),
                            f"Culled {culled} low-quality photos")

    return trip_data


def _run_skeleton(session: SessionConfig, trip_data: dict, progress_callback=None) -> "Trip":
    """Build skeleton from ingested data."""
    from post_trip_summary.pipeline.skeleton import build_skeleton
    gap = session.settings.get("cluster_time_gap_minutes", 15)
    dist = session.settings.get("cluster_distance_meters", 200)
    return build_skeleton(trip_data, gap_minutes=gap, distance_meters=dist,
                         progress_callback=progress_callback)
```

- [ ] **Step 6: Write test for run_ingest_pipeline**

Create `tests/test_compute.py`:

```python
"""Test the wizard compute pipeline wrapper."""
from pathlib import Path
from datetime import datetime
from PIL import Image
from post_trip_summary.config import create_session


def _create_photo(directory: Path, name: str, timestamp: datetime, lat: float = 48.858, lon: float = 2.294):
    """Create a minimal JPEG with EXIF-like data for testing."""
    img_path = directory / f"{name}.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(img_path, "JPEG")
    return img_path


def test_run_ingest_pipeline_with_progress(tmp_path):
    """End-to-end: ingest photos, build skeleton, report progress."""
    from unittest.mock import patch, MagicMock

    # Create session with photos
    session = create_session("test-trip", base_dir=tmp_path)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    _create_photo(photos_dir, "IMG_001", datetime(2026, 3, 5, 10, 0))
    _create_photo(photos_dir, "IMG_002", datetime(2026, 3, 5, 10, 5))
    session.inputs["photos"] = str(photos_dir)
    session.current_stage = "setup"
    session.save()

    progress_calls = []
    def mock_callback(phase, current, total, label=""):
        progress_calls.append((phase, current, total, label))

    from post_trip_summary.server.compute import run_ingest_pipeline

    # Mock reverse_geocode to avoid network calls
    mock_geo = {"name": "Test Place", "city": "Paris", "country": "France",
                "address": "123 Test St", "lat": 48.858, "lon": 2.294}
    with patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo):
        trip = run_ingest_pipeline(session, progress_callback=mock_callback)

    # Verify trip was built
    assert trip is not None
    assert len(trip.days) > 0

    # Verify progress was reported
    phases = {call[0] for call in progress_calls}
    assert "scanning" in phases  # Photo scanning phase
    assert "scoring" in phases   # Quality scoring phase

    # Verify files were saved
    assert (session.stage_file("ingested")).exists()
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest tests/test_compute.py tests/test_progress.py -v`
Expected: PASS

- [ ] **Step 8: Run full test suite**

Run: `python -m pytest -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/post_trip_summary/server/compute.py src/post_trip_summary/pipeline/ingest/photos.py src/post_trip_summary/pipeline/quality.py src/post_trip_summary/pipeline/skeleton.py tests/test_compute.py
git commit -m "Add progress callbacks to pipeline and ingest compute wrapper"
```

---

### Task 4: Progress Page Template

**Files:**
- Create: `src/post_trip_summary/templates/progress.html`
- Modify: `src/post_trip_summary/server/app.py` (replace ingest placeholder with progress page)
- Test: `tests/test_server_app.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_server_app.py`:

```python
def test_ingest_page_renders(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "setup"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.get("/wizard/ingest")
    assert response.status_code == 200
    assert "progress" in response.text.lower() or "Processing" in response.text
```

- [ ] **Step 2: Create progress.html template**

Create `src/post_trip_summary/templates/progress.html`:

```html
{% extends "wizard.html" %}
{% block title %}{{ stage_title }}{% endblock %}

{% block extra_css %}
.progress-container { max-width: 600px; margin: 3rem auto; text-align: center; }
.progress-card { background: #16213e; border-radius: 12px; padding: 2rem; }
.stage-title { font-size: 1.3rem; margin-bottom: 1.5rem; }
.progress-bar-track { background: #0f3460; border-radius: 8px; height: 8px; margin: 1rem 0; overflow: hidden; }
.progress-bar-fill { background: #2ecc71; height: 100%; border-radius: 8px; transition: width 0.3s ease; width: 0%; }
.progress-bar-fill.indeterminate { width: 30%; animation: slide 1.5s infinite ease-in-out; }
@keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(400%); } }
.progress-label { color: #aaa; font-size: 0.9rem; margin-top: 0.5rem; min-height: 1.5em; }
.progress-stats { color: #888; font-size: 0.85rem; margin-top: 1rem; }
.error-message { color: #e74c3c; margin-top: 1rem; }
{% endblock %}

{% block content %}
<div class="progress-container">
  <div class="progress-card">
    <div class="stage-title" id="stage-title">{{ stage_title }}</div>
    <div class="progress-bar-track">
      <div class="progress-bar-fill indeterminate" id="progress-bar"></div>
    </div>
    <div class="progress-label" id="progress-label">Starting...</div>
    <div class="progress-stats" id="progress-stats"></div>
    <div class="error-message" id="error-message" style="display: none;"></div>
  </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
const phaseLabels = {
  scanning: "Scanning Photos",
  scoring: "Scoring Quality",
  supplementary: "Parsing Data Sources",
  skeleton: "Building Skeleton",
};

function connectSSE() {
  const source = new EventSource("/api/progress");
  const bar = document.getElementById("progress-bar");
  const label = document.getElementById("progress-label");
  const stats = document.getElementById("progress-stats");
  const title = document.getElementById("stage-title");
  const errorEl = document.getElementById("error-message");

  source.addEventListener("state", function(e) {
    const state = JSON.parse(e.data);

    if (state.done) {
      source.close();
      bar.classList.remove("indeterminate");
      bar.style.width = "100%";
      label.textContent = "Complete!";
      setTimeout(() => { window.location.href = "/wizard/" + (state.next_stage || "review"); }, 1000);
      return;
    }

    if (state.failed) {
      source.close();
      bar.classList.remove("indeterminate");
      bar.style.width = "0%";
      bar.style.background = "#e74c3c";
      label.textContent = "Failed";
      errorEl.textContent = state.error;
      errorEl.style.display = "block";
      return;
    }

    if (state.phase) {
      title.textContent = phaseLabels[state.phase] || state.phase;
    }

    if (state.total > 0) {
      const pct = Math.round((state.current / state.total) * 100);
      bar.classList.remove("indeterminate");
      bar.style.width = pct + "%";
      stats.textContent = state.current + " / " + state.total;
    } else {
      bar.classList.add("indeterminate");
      stats.textContent = "";
    }

    label.textContent = state.label || "";
  });

  source.onerror = function() {
    // Reconnect after brief delay
    source.close();
    setTimeout(connectSSE, 2000);
  };
}

// Auto-start ingest if stage is "setup" (user just clicked Start Processing)
{% if auto_start %}
fetch("/api/stage/start", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({stage: "{{ compute_stage }}"})
}).then(resp => {
  if (resp.ok) { connectSSE(); }
  else { resp.json().then(d => {
    document.getElementById("error-message").textContent = d.detail || "Failed to start";
    document.getElementById("error-message").style.display = "block";
  }); }
}).catch(err => {
  document.getElementById("error-message").textContent = "Network error: " + err.message;
  document.getElementById("error-message").style.display = "block";
});
{% else %}
connectSSE();
{% endif %}
</script>
{% endblock %}
```

- [ ] **Step 3: Replace ingest placeholder with progress page route**

In `src/post_trip_summary/server/app.py`, remove "ingest" from the placeholder loop and add a dedicated route:

```python
    @app.get("/wizard/ingest", response_class=HTMLResponse)
    def wizard_ingest():
        ctx = _get_wizard_context(app.state.session)
        ctx["stage_title"] = "Processing Trip Data"
        ctx["compute_stage"] = "ingest"
        # Auto-start if arriving from setup (stage is "setup")
        ctx["auto_start"] = app.state.session.current_stage == "setup"
        template = env.get_template("progress.html")
        return template.render(**ctx)

    # Update placeholder loop to exclude "ingest"
    for step_name in ["review", "enrich", "highlights", "generate"]:
        _register_placeholder_step(app, env, step_name)
```

Also update the setup page's JS redirect: instead of `window.location.href = "/wizard/ingest"`, it should go to `/wizard/ingest` which will auto-start the compute.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_server_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/templates/progress.html src/post_trip_summary/server/app.py tests/test_server_app.py
git commit -m "Add progress page template with SSE and auto-start ingest"
```

---

### Task 5: Integration Test — Full Ingest Flow

**Files:**
- Modify: `tests/test_wizard_integration.py`

- [ ] **Step 1: Write integration test**

Add to `tests/test_wizard_integration.py`:

```python
import time
from datetime import datetime
from PIL import Image
from unittest.mock import patch


def _create_test_photos(directory, count=3):
    """Create minimal test JPEG files."""
    for i in range(count):
        img_path = directory / f"IMG_{i:04d}.jpg"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path, "JPEG")


def test_setup_to_ingest_flow(tmp_path):
    """Simulate: setup inputs -> start ingest -> check progress -> completion."""
    from post_trip_summary.config import create_session, load_session
    from post_trip_summary.server.app import create_app

    # Setup session with photos
    session = create_session("test-trip", base_dir=tmp_path)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    _create_test_photos(photos_dir, count=3)
    session.inputs["photos"] = str(photos_dir)
    session.current_stage = "setup"
    session.save()

    app = create_app(session)
    client = TestClient(app)

    # Mock reverse_geocode to avoid network calls
    mock_geo = {"name": "Test Place", "city": "Paris", "country": "France",
                "address": "123 Test St", "lat": 48.858, "lon": 2.294}
    with patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo):
        # Start ingest
        response = client.post("/api/stage/start", json={"stage": "ingest"})
        assert response.status_code == 200

        # Wait for completion (poll progress)
        for _ in range(30):
            time.sleep(0.5)
            state = app.state.progress.get_state()
            if state["done"] or state["failed"]:
                break

    assert state["done"] is True, f"Expected done, got: {state}"
    assert app.state.session.current_stage == "ingested"
    assert app.state.trip is not None
```

- [ ] **Step 2: Run integration test**

Run: `python -m pytest tests/test_wizard_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_wizard_integration.py
git commit -m "Add integration test for full ingest flow"
```

---

## Verification

After all tasks are complete:

1. `python -m pytest -v` — all tests pass
2. Manual test:
   ```
   post-trip-summary new "Test Trip"
   post-trip-summary start test-trip
   ```
   - Fill in photos path on Setup page
   - Click "Start Processing"
   - Progress page shows live updates: Scanning Photos → Scoring Quality → Building Skeleton
   - Auto-transitions to Review placeholder page when done
3. Progress bar updates in real time via SSE

## What's Next (Phase 3)

Phase 3 will add the Review page — combined skeleton review + photo culling, migrating the existing skeleton_review.html and photo_review.html functionality into a unified wizard step.
