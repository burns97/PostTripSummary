# Wizard Phase 3: Combined Review Page

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Review placeholder with a working combined skeleton review + photo culling page, so the user can edit events and cull photos in one unified step.

**Architecture:** Migrate existing API endpoints from `preview/server.py` into the wizard `server/app.py`. Create a new `review.html` template combining skeleton editing and photo culling. Add save/advance logic to persist changes and move to the Enrich step.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, vanilla JS

**Spec:** `docs/superpowers/specs/2026-03-22-browser-gui-wizard-design.md` — Review Step (Step 3)

---

### Task 1: Add Review API Endpoints to Wizard Server

**Files:**
- Modify: `src/post_trip_summary/server/app.py`
- Test: `tests/test_server_app.py`

Migrate all review-related endpoints from `preview/server.py` into `create_app()`. These operate on `app.state.trip` and call a save function after each mutation.

- [ ] **Step 1: Add helper functions for save and index rebuild**

Add inside `create_app()` in `server/app.py`:

```python
    def _save_trip():
        """Persist current trip state to the reviewed stage file."""
        from post_trip_summary.serialization import save_trip as _save
        # Save to the file matching the current stage
        stage = app.state.session.current_stage
        if stage in ("ingested", "reviewed"):
            _save(app.state.trip, app.state.session.stage_file("reviewed"))
        else:
            _save(app.state.trip, app.state.session.stage_file(stage))

    def _rebuild_index():
        """Rebuild event index and clear thumbnail cache after structural changes."""
        app.state.event_index = _build_event_index(app.state.trip)
        app.state.thumb_cache.clear()
```

- [ ] **Step 2: Add skeleton API endpoints**

Add these endpoints inside `create_app()`:

```python
    @app.post("/api/skeleton/merge")
    async def skeleton_merge(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import merge_events
        data = await request.json()
        day_index = data["day_index"]
        event_ids = data["event_ids"]
        new_name = data["new_name"]
        if day_index < 0 or day_index >= len(app.state.trip.days):
            raise HTTPException(400, "invalid day_index")
        day = app.state.trip.days[day_index]
        try:
            merged = merge_events(day, event_ids)
        except ValueError as e:
            raise HTTPException(400, str(e))
        merged.name = new_name
        _rebuild_index()
        _save_trip()
        return {"merged_event": _serialize_event(merged),
                "day_events": [_serialize_event(e) for e in day.events]}

    @app.post("/api/skeleton/rename")
    async def skeleton_rename(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import rename_event
        data = await request.json()
        event = app.state.event_index.get(data["event_id"])
        if not event:
            raise HTTPException(404, "event not found")
        rename_event(event, data["new_name"])
        _save_trip()
        return {"event_id": event.id, "new_name": event.name}

    @app.post("/api/skeleton/delete")
    async def skeleton_delete(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import delete_event
        data = await request.json()
        event_id = data["event_id"]
        target_day = None
        day_index = -1
        for i, day in enumerate(app.state.trip.days):
            for ev in day.events:
                if ev.id == event_id:
                    target_day = day
                    day_index = i
                    break
            if target_day:
                break
        if not target_day:
            raise HTTPException(404, "event not found")
        try:
            removed = delete_event(target_day, event_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
        _rebuild_index()
        _save_trip()
        return {"deleted": removed.id, "day_index": day_index,
                "remaining_events": len(target_day.events)}

    @app.post("/api/skeleton/update-type")
    async def skeleton_update_type(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import change_event_type
        data = await request.json()
        event = app.state.event_index.get(data["event_id"])
        if not event:
            raise HTTPException(404, "event not found")
        try:
            change_event_type(event, data["new_type"])
        except ValueError as e:
            raise HTTPException(400, str(e))
        _save_trip()
        return {"event_id": event.id, "new_type": event.type}

    @app.post("/api/skeleton/add-note")
    async def skeleton_add_note(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import set_event_note
        data = await request.json()
        event = app.state.event_index.get(data["event_id"])
        if not event:
            raise HTTPException(404, "event not found")
        set_event_note(event, data["note"])
        _save_trip()
        return {"event_id": event.id, "note": event.notes}

    @app.post("/api/skeleton/suggest-merge-name")
    async def skeleton_suggest_merge_name(request: Request):
        from post_trip_summary.pipeline.skeleton_ops import suggest_merge_name
        data = await request.json()
        events = [app.state.event_index.get(eid) for eid in data["event_ids"]]
        events = [e for e in events if e is not None]
        if len(events) < 2:
            raise HTTPException(400, "need at least 2 valid events")
        return {"suggested_name": suggest_merge_name(events)}

    @app.post("/api/toggle-keep")
    async def toggle_keep(request: Request):
        data = await request.json()
        event = app.state.event_index.get(data["event_id"])
        if not event:
            raise HTTPException(404, "event not found")
        idx = data["photo_index"]
        if idx < 0 or idx >= len(event.photos):
            raise HTTPException(400, "invalid photo index")
        photo = event.photos[idx]
        photo.is_kept = not photo.is_kept
        _save_trip()
        kept = sum(1 for p in event.photos if p.is_kept)
        return {"is_kept": photo.is_kept, "kept_count": kept, "total": len(event.photos)}

    @app.post("/api/bulk-action")
    async def bulk_action(request: Request):
        data = await request.json()
        event = app.state.event_index.get(data["event_id"])
        if not event:
            raise HTTPException(404, "event not found")
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
        else:
            raise HTTPException(400, "unknown action")
        _save_trip()
        kept = sum(1 for p in event.photos if p.is_kept)
        return {"action": action, "affected": count, "kept_count": kept, "total": len(event.photos)}

    @app.post("/api/update-description")
    async def update_description(request: Request):
        data = await request.json()
        event = app.state.event_index.get(data["event_id"])
        if not event:
            raise HTTPException(404, "event not found")
        event.description = data.get("description", "")
        _save_trip()
        return {"event_id": event.id, "description": event.description}

    @app.post("/api/stage/advance")
    async def advance_stage(request: Request):
        """Advance to the next wizard stage."""
        from post_trip_summary.config import STAGES
        current = app.state.session.current_stage
        idx = STAGES.index(current)
        if idx + 1 < len(STAGES):
            app.state.session.current_stage = STAGES[idx + 1]
            app.state.session.save()
            _save_trip()
        step = STAGE_TO_STEP.get(app.state.session.current_stage, "review")
        return {"stage": app.state.session.current_stage, "next_step": step}
```

Also add the `_serialize_event` helper outside `create_app()`:

```python
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
```

- [ ] **Step 3: Write tests for key endpoints**

Add to `tests/test_server_app.py` — tests that create a trip with events and verify the endpoints work:

```python
def test_toggle_keep(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/toggle-keep", json={"event_id": "day01-event01", "photo_index": 0})
    assert response.status_code == 200
    data = response.json()
    assert data["is_kept"] is False  # was True, now toggled


def test_skeleton_rename(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/skeleton/rename", json={"event_id": "day01-event01", "new_name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["new_name"] == "Renamed"


def test_advance_stage(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/stage/advance")
    assert response.status_code == 200
    assert response.json()["stage"] == "reviewed"
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_server_app.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "Add review API endpoints to wizard server"
```

---

### Task 2: Create Review Template and Route

**Files:**
- Create: `src/post_trip_summary/templates/review.html`
- Modify: `src/post_trip_summary/server/app.py` (replace review placeholder with real route)
- Test: `tests/test_server_app.py`

This is the largest task — creating the combined skeleton review + photo cull template. It adapts the existing `skeleton_review.html` and `photo_review.html` patterns into one wizard page.

- [ ] **Step 1: Create `review.html` template**

Create `src/post_trip_summary/templates/review.html` extending `wizard.html`. The template combines:

**Layout structure:**
- Sticky stats bar below wizard steps: event count, photo count, kept/removed, "Continue to Enrichment" button
- Collapsible `<details>` sections per day
- Event cards within each day

**Per-event card:**
- Header row: checkbox (for merge), type icon + select dropdown, editable name input, time range, photo count badge, source badges, action buttons (delete)
- Expandable photo grid (225x168 thumbnails, click to toggle kept/removed, quality badges, bulk keep/remove buttons)
- Description textarea (auto-saves on blur)
- Notes textarea (auto-saves on blur)

**JavaScript functions (adapted from existing templates):**
- `togglePhoto(card)` — POST `/api/toggle-keep`, update card classes
- `bulkAction(eventId, action)` — POST `/api/bulk-action`, update all cards
- `onRenameBlur(input)` — POST `/api/skeleton/rename`
- `deleteEvent(eventId, dayIndex)` — POST `/api/skeleton/delete` with confirm
- `changeType(select)` — POST `/api/skeleton/update-type`
- `onNoteBlur(input)` — POST `/api/skeleton/add-note`
- `onDescriptionBlur(textarea)` — POST `/api/update-description`
- `getSelected()`, `updateSelection()`, `openMergePrompt()`, `confirmMerge()` — merge workflow
- `updateGlobalStats()` — count events, photos, kept
- `continueToNext()` — POST `/api/stage/advance`, redirect to next step

**CSS:** Dark theme matching existing templates (#1a1a2e, #16213e, #0f3460). Photo cards 225x168. Event cards with border, type-colored left accent.

**Template variables:** `trip`, `type_icons` dict

- [ ] **Step 2: Replace review placeholder with real route**

In `server/app.py`, remove "review" from the placeholder loop and add:

```python
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
```

- [ ] **Step 3: Write test for review page rendering**

```python
def test_review_page_renders_with_trip(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/wizard/review")
    assert response.status_code == 200
    assert "day01-event01" in response.text
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "Add combined review page with skeleton editing and photo culling"
```

---

### Task 3: Integration Test — Review Flow

**Files:**
- Modify: `tests/test_wizard_integration.py`

- [ ] **Step 1: Write integration test**

Test the full review flow: load trip, render review page, toggle a photo, rename an event, advance stage.

```python
def test_review_flow(tmp_path):
    """Test review page: toggle photo, rename event, advance stage."""
    from post_trip_summary.config import create_session
    from post_trip_summary.server.app import create_app, _build_event_index

    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()

    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)  # reuse helper
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)

    # Review page renders
    response = client.get("/wizard/review")
    assert response.status_code == 200

    # Toggle a photo
    response = client.post("/api/toggle-keep", json={"event_id": "day01-event01", "photo_index": 0})
    assert response.status_code == 200

    # Rename event
    response = client.post("/api/skeleton/rename", json={"event_id": "day01-event01", "new_name": "Test Landmark"})
    assert response.status_code == 200

    # Advance to enrich
    response = client.post("/api/stage/advance")
    assert response.status_code == 200
    assert session.current_stage == "reviewed"
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git commit -m "Add integration test for review flow"
```

---

## Verification

1. `python -m pytest -v` — all tests pass
2. Manual test: `post-trip-summary resume <slug>` after ingest
   - Review page shows all days and events
   - Can expand events to see photo grid
   - Click photos to toggle kept/removed
   - Inline edit event names, types, notes, descriptions
   - Merge events within a day
   - Delete events
   - "Continue" button advances to Enrich step
