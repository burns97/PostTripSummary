# Wizard Phase 4: Enrich + Highlights

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the Enrich compute stage (with browser-based cost gate) and the Highlights interactive page, completing steps 4 and 5 of the wizard.

**Architecture:** Enrich reuses the SSE progress infrastructure from Phase 2. A new cost estimate API powers the browser cost gate. The highlights page is similar to Review but focused on highlight selection with AI descriptions visible.

---

### Task 1: Enrich Compute Wrapper + Cost Estimate API

**Files:**
- Modify: `src/post_trip_summary/server/compute.py` — add `run_enrich_pipeline`
- Modify: `src/post_trip_summary/server/app.py` — add cost estimate endpoint, extend `api/stage/start` for enrich
- Modify: `src/post_trip_summary/pipeline/enrich.py` — add `progress_callback` parameter
- Test: `tests/test_server_app.py`, `tests/test_compute.py`

The enrich wrapper needs to:
- Accept a `mode` parameter: "full", "reduced", or "skip"
- Run `enrich_trip()` with progress reporting
- The existing `enrich_trip()` uses `click.echo` and `click.prompt` — create a new function `enrich_trip_headless()` that takes a provider, trip, enrichment plan, and progress_callback, skipping CLI interaction

- [ ] **Step 1: Add `enrich_trip_headless` to enrich.py**

Add a new function to `src/post_trip_summary/pipeline/enrich.py` that runs enrichment without CLI interaction:

```python
def enrich_trip_headless(trip: Trip, mode: str = "full", progress_callback=None) -> Trip:
    """Run vision enrichment without CLI interaction. For wizard server use."""
    vs = get_vision_settings()
    if not vs.get("api_key"):
        # No API key — just select highlights
        for day in trip.days:
            for event in day.events:
                if event.photos:
                    _select_highlights(event.photos)
        return trip

    provider = create_provider(vs["provider"], api_key=vs.get("api_key"), model=vs.get("model"))
    all_events = [event for day in trip.days for event in day.events if event.photos]
    enrichment_plan = plan_enrichment(all_events)

    if mode == "reduced":
        enrichment_plan = [p for p in enrichment_plan if p["purpose"] != "scene"]
    elif mode == "skip":
        for event in all_events:
            _select_highlights(event.photos)
        return trip

    total_images = sum(len(item["photos"]) for item in enrichment_plan)
    if total_images == 0:
        return trip

    # Pass 1: Per-photo analysis
    from post_trip_summary.vision.gemini import QuotaExhaustedError
    from post_trip_summary.vision.prompts import build_context

    analyzed = 0
    quota_exhausted = False
    event_count = len(enrichment_plan)

    for event_idx, item in enumerate(enrichment_plan, 1):
        event = item["event"]
        photos = item["photos"]
        purpose = item["purpose"]

        loc = event.location
        context = build_context(
            timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
            city=loc.city if loc else "",
            country=loc.country if loc else "",
            poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
        )

        best_description = ""
        best_landmark = None

        for photo in photos:
            if quota_exhausted:
                break
            if progress_callback:
                progress_callback("analyzing", analyzed + 1, total_images,
                                f"[{event_idx}/{event_count}] {event.name}")
            try:
                image_data, media_type = _read_image(photo.path)
                result = provider.analyze(image_data, media_type, purpose, context=context)
                photo.ai_description = result.description
                analyzed += 1
                if result.landmark and not best_landmark:
                    best_landmark = result.landmark
                if result.description and not best_description:
                    best_description = result.description
            except QuotaExhaustedError:
                quota_exhausted = True
            except Exception:
                pass

        if best_description and not event.description:
            event.description = best_description
        if best_landmark and event.name in ("Unknown", event.location.city, ""):
            event.name = best_landmark

        _select_highlights(event.photos)

    # Pass 2: Synthesis
    if not quota_exhausted:
        from post_trip_summary.vision.prompts import get_prompt
        synth_count = 0
        for item in enrichment_plan:
            event = item["event"]
            described_highlights = [
                p for p in event.photos
                if p.is_kept and p.is_highlight and p.ai_description
            ]
            if len(described_highlights) < 2:
                continue
            if progress_callback:
                progress_callback("synthesizing", synth_count + 1, 0, f"Synthesizing: {event.name}")
            desc_lines = [f"{i+1}. {p.ai_description}" for i, p in enumerate(described_highlights)]
            loc = event.location
            context = build_context(
                timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
                city=loc.city if loc else "",
                country=loc.country if loc else "",
                poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
            )
            prompt = get_prompt("synthesize", context=context,
                              image_count=len(described_highlights),
                              descriptions="\n".join(desc_lines))
            try:
                event.description = provider.synthesize(prompt)
                synth_count += 1
            except Exception:
                pass

    return trip
```

- [ ] **Step 2: Add `run_enrich_pipeline` to compute.py**

```python
def run_enrich_pipeline(session: SessionConfig, mode: str = "full", progress_callback=None):
    """Run enrichment pipeline with progress reporting."""
    start_time = time.time()
    logger.info("=== Starting enrichment pipeline (mode=%s) ===", mode)
    cb = _logging_callback(progress_callback)

    from post_trip_summary.serialization import load_trip
    trip = load_trip(session.stage_file("reviewed"))

    from post_trip_summary.pipeline.enrich import enrich_trip_headless
    trip = enrich_trip_headless(trip, mode=mode, progress_callback=cb)

    save_trip(trip, session.stage_file("enriched"))

    elapsed = time.time() - start_time
    logger.info("=== Enrichment complete in %.1fs ===", elapsed)
    return trip
```

- [ ] **Step 3: Add cost estimate endpoint and extend stage/start in app.py**

Add cost estimate endpoint:
```python
    @app.get("/api/enrich/estimate")
    def enrich_estimate():
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        from post_trip_summary.vision.triage import plan_enrichment, estimate_batch_cost
        from post_trip_summary.vision.client import create_provider
        vs = get_vision_settings()
        all_events = [e for d in app.state.trip.days for e in d.events if e.photos]
        plan = plan_enrichment(all_events)
        total = sum(len(item["photos"]) for item in plan)
        reduced_plan = [p for p in plan if p["purpose"] != "scene"]
        reduced_total = sum(len(item["photos"]) for item in reduced_plan)
        cost = 0.0
        if vs.get("api_key"):
            try:
                provider = create_provider(vs["provider"], api_key=vs.get("api_key"), model=vs.get("model"))
                cost = estimate_batch_cost(total, provider)
            except Exception:
                pass
        return JSONResponse({
            "provider": vs.get("provider", "gemini"),
            "model": vs.get("model", ""),
            "total_images": total,
            "reduced_images": reduced_total,
            "estimated_cost": cost,
            "has_api_key": bool(vs.get("api_key")),
            "event_count": len(plan),
        })
```

Extend `api/stage/start` to handle "enrich":
```python
        elif stage == "enrich":
            mode = body.get("mode", "full")  # full, reduced, skip
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
```

- [ ] **Step 4: Write tests, run full suite, commit**

Commit: `git commit -m "Add enrich compute wrapper, cost estimate API, and headless enrichment"`

---

### Task 2: Enrich Page with Cost Gate

**Files:**
- Create: `src/post_trip_summary/templates/enrich.html`
- Modify: `src/post_trip_summary/server/app.py` — replace enrich placeholder

The enrich page has two states:
1. **Cost gate** — shown first, fetches `/api/enrich/estimate` and displays cost info with Approve/Reduce/Skip buttons
2. **Progress** — after approval, starts enrichment and shows SSE progress (reuse progress pattern)

- [ ] **Step 1: Create enrich.html**

Template extends wizard.html with:
- Cost gate card: provider, model, image count, estimated cost, three buttons
- Progress card (hidden initially): same pattern as progress.html
- JS: fetch estimate on load, show cost gate, on approve → POST /api/stage/start with mode, then connect SSE

- [ ] **Step 2: Add route in app.py**

```python
    @app.get("/wizard/enrich", response_class=HTMLResponse)
    def wizard_enrich():
        if app.state.trip is None:
            return RedirectResponse("/wizard/setup", status_code=307)
        if app.state.session.current_stage not in ("reviewed", "enriched"):
            step = STAGE_TO_STEP.get(app.state.session.current_stage, "setup")
            if step != "enrich":
                return RedirectResponse(f"/wizard/{step}", status_code=307)
        ctx = _get_wizard_context(app.state.session)
        ctx["stage_title"] = "Vision Enrichment"
        template = env.get_template("enrich.html")
        return HTMLResponse(template.render(**ctx))
```

Remove "enrich" from placeholder loop.

- [ ] **Step 3: Test, commit**

Commit: `git commit -m "Add enrich page with cost gate and progress"`

---

### Task 3: Highlights Page

**Files:**
- Create: `src/post_trip_summary/templates/highlights.html`
- Modify: `src/post_trip_summary/server/app.py` — add toggle-highlight endpoint, replace highlights placeholder

The highlights page shows events with only kept photos. Click to toggle highlight. Shows AI descriptions.

- [ ] **Step 1: Add toggle-highlight and highlight bulk endpoints to app.py**

```python
    @app.post("/api/toggle-highlight")
    async def toggle_highlight(request: Request):
        body = await request.json()
        event = app.state.event_index.get(body.get("event_id"))
        if not event:
            raise HTTPException(404, "Event not found")
        idx = body.get("photo_index")
        photo = event.photos[idx]
        photo.is_highlight = not photo.is_highlight
        _save_trip()
        highlighted = sum(1 for p in event.photos if p.is_kept and p.is_highlight)
        kept = sum(1 for p in event.photos if p.is_kept)
        return JSONResponse({"is_highlight": photo.is_highlight,
                           "highlighted_count": highlighted, "kept_count": kept})
```

Also extend bulk-action to support "highlight_all" and "highlight_none".

- [ ] **Step 2: Create highlights.html**

Extends wizard.html. Per event:
- Event header (name, type icon, time range) — read-only
- Photo grid showing only kept photos, click to toggle highlight (yellow glow vs dimmed)
- AI description tooltip on hover
- Bulk: "Highlight All" / "Clear Highlights"
- Editable description and notes fields
- Stats: highlighted / kept counts
- "Continue to Generate" button

- [ ] **Step 3: Add route, remove from placeholders**

```python
    @app.get("/wizard/highlights", response_class=HTMLResponse)
    def wizard_highlights():
        if app.state.trip is None:
            return RedirectResponse("/wizard/setup", status_code=307)
        ctx = _get_wizard_context(app.state.session)
        ctx["trip"] = app.state.trip
        ctx["type_icons"] = TYPE_ICONS
        template = env.get_template("highlights.html")
        return HTMLResponse(template.render(**ctx))
```

- [ ] **Step 4: Test, commit**

Commit: `git commit -m "Add highlights page with photo selection and AI descriptions"`

---

### Task 4: Integration Test

**Files:**
- Modify: `tests/test_wizard_integration.py`

Test: cost estimate API returns data, stage advance from reviewed to enriched works, highlights page renders.

Commit: `git commit -m "Add integration tests for enrich and highlights"`
