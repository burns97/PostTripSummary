# Browser-Based GUI Wizard

## Summary

Shift the post-trip-summary pipeline from CLI-driven orchestration to a browser-based wizard. The user runs one CLI command (`post-trip-summary start <slug>`) which launches a FastAPI server and opens the browser. All subsequent interaction — setup, compute stages, review, generation — happens in the browser.

## Decisions

- **Entry point:** CLI creates the session (`new`), browser handles everything after (`start`/`resume` launches the server).
- **Compute stages:** Show a progress page with real-time updates via SSE. Auto-transition to the next step when done.
- **Review consolidation:** Skeleton review and photo culling are combined into one step. The user sees event structure and photos together.
- **Detail editing:** Event descriptions and notes are editable throughout (in both Review and Highlights steps), not a dedicated step.
- **Generate:** Explicit generate page with output toggles, generate button, and preview/download links.
- **Navigation:** Linear wizard with step indicator. Completed steps are revisitable. Going back and making changes invalidates later steps with a warning.
- **Tech stack:** Extend existing FastAPI + Jinja2 + vanilla JS. SSE for progress streaming. No new frontend frameworks.

## Wizard Steps

```
[1. Setup] → [2. Ingest] → [3. Review] → [4. Enrich] → [5. Highlights] → [6. Generate]
```

| Step | Type | Description |
|------|------|-------------|
| 1. Setup | Interactive | Confirm/edit input paths, add supplementary sources, configure vision provider settings |
| 2. Ingest | Compute | Scan photos, quality score, auto-cull, parse supplementary data, build skeleton, reverse geocode |
| 3. Review | Interactive | Combined skeleton review + photo culling. Merge/rename/delete/retype events, cull photos, edit descriptions and notes |
| 4. Enrich | Compute | Cost gate (approve/reduce/skip), vision API analysis with progress, synthesis pass, auto-select highlights |
| 5. Highlights | Interactive | Pick/adjust highlight photos, edit event descriptions and notes, view AI descriptions |
| 6. Generate | Interactive | Toggle output types, generate, preview results, download/open outputs |

## CLI Changes

- `post-trip-summary new <name>` — simplified. Creates session with a slug only. The `--photos` and `--excel` flags are removed. All input path configuration (photos dir, Excel itinerary, supplementary sources) is deferred to the Setup wizard step. The interactive prompts for photos/excel paths are removed.
- `post-trip-summary start <slug>` — new command, launches FastAPI server and opens browser at the wizard. Server runs until Ctrl+C.
- `post-trip-summary resume <slug>` — alias for `start`, opens the wizard at whatever stage the session is on. The `--from` flag is removed; going back to earlier stages is handled by the wizard's back-navigation and stage invalidation.
- `post-trip-summary list`, `delete`, `config` — unchanged.
- `cull-photos`, `review-skeleton`, `pick-highlights`, `add-input` — deprecated, replaced by wizard steps.
- `post-trip-summary preview <slug>` — kept for backward compatibility, uses new server internals.

## Compute Stage UI

Both Ingest (step 2) and Enrich (step 4) use the same progress page pattern.

### Progress Page Layout

Centered card showing:
- Stage title (e.g., "Scanning Photos...")
- Progress bar (determinate when count is known, indeterminate otherwise)
- Current item label (e.g., "Processing IMG_4521.jpg", "Reverse geocoding cluster 8/12")
- Running stats (e.g., "142 photos scanned, 8 with GPS, 3 skipped")

### Ingest Sub-phases

Run in sequence on the same progress card:
1. Scan photos (N/total files)
2. Quality scoring + auto-cull (N/total photos)
3. Parse supplementary data (status line per source)
4. Build skeleton — cluster + reverse geocode (N/total clusters)

Auto-transitions to Review when done.

### Enrich Cost Gate

Before API calls, shows cost estimate card: provider, model, photo count, estimated cost. Three buttons: Approve / Reduce Scope / Skip. After approval, switches to progress view. Auto-transitions to Highlights when done.

### SSE Implementation

- Browser opens `GET /api/progress` SSE connection
- Server holds at most one active background task at a time. The SSE endpoint always streams from that task. No stage scoping needed — the server knows which stage is running.
- Server runs compute in background thread via `asyncio.to_thread()`
- Progress events: `{"phase": "photos", "current": 42, "total": 350, "label": "IMG_4521.jpg"}`
- Completion event: `{"phase": "done", "next_stage": "review"}`
- Thread-safe progress object (dataclass or queue) shared between pipeline thread and SSE endpoint
- If the SSE connection drops (browser closed/refreshed), the compute continues. On reconnect, the browser reads current progress state and resumes display. If compute already finished, the browser sees the "done" state and navigates to the next step.
- During compute stages, the Trip object may be in a partially-mutated state. The wizard UI disables navigation to other steps while a compute stage is running.

## Review Step (Step 3)

Combined skeleton review + photo culling in one page.

### Per-event Layout

- Event header: inline-editable name, type dropdown (with icons), time range, source badges
- Expandable photo grid (225x168 thumbnails)
  - Click to toggle kept/removed (green border vs red/dimmed)
  - Bulk actions: "Keep All" / "Remove All"
  - Quality badge per photo
- Notes textarea (auto-saves on blur)
- Description field (editable, pre-populated after enrichment if revisiting)

### Day Grouping

Collapsible day sections, each containing events.

### Skeleton Operations

- Checkbox selection on events for merge
- "Merge Selected" button in day header
- Delete event button
- Type change dropdown

### Stats Bar

Sticky bar below wizard indicator: total events, total photos, kept/removed counts, "Continue" button.

## Highlights Step (Step 5)

Same day/event structure as Review, but focused on highlight selection.

### Per-event Layout

- Event header: name, type icon, time range (read-only; editing triggers invalidation warning)
- Photo grid showing only kept photos
  - Click to toggle highlight (yellow border + glow vs dimmed)
  - Hover shows `photo.ai_description` tooltip
  - Bulk actions: "Highlight All" / "Clear Highlights"
- Editable description field (shows synthesized or single-photo description)
- Editable notes field

### Stats Bar

Highlighted count / kept count (per event and overall), "Continue to Generate" button.

## Setup Step (Step 1)

Displays session name and all configured input paths.

- Photo directory path (required, already set at `new` time)
- Optional sources with status: Excel itinerary, credit card CSV, Google Maps JSON, Apple Health XML, Day One JSON. Each shows path if configured or "Add" button.
- File paths as text inputs (server validates existence)
- Vision provider settings: provider dropdown, model, API key status
- "Start Processing" button initiates ingest

## Generate Step (Step 6)

- Checkboxes for output types (all checked by default):
  - Detailed record (HTML)
  - Shareable summary (HTML/PDF)
  - Blog post (HTML)
  - Photo prep (copy highlights to output folder)
- "Generate" button with progress indicator
- Results section: each output as a card with "Preview" link (new tab) and file path
- "Done" button — displays a "Processing complete. You can close this tab and stop the server with Ctrl+C in the terminal." message. (Programmatic server shutdown from a request handler is unreliable on Windows.)

## Stage Invalidation

Going back to a completed step and making changes invalidates later steps. The wizard shows a warning before allowing edits. User confirms or cancels.

**Invalidation map — editing a step clears these files and resets progress:**

| Editing step | Files cleared | Warning |
|-------------|--------------|---------|
| Setup (paths changed) | `trip_data.json`, `trip_reviewed.json`, `trip_enriched.json`, `trip_final.json`, `output/` | "All processing will need to re-run." |
| Review (merge/delete/rename) | `trip_enriched.json`, `trip_final.json` | "Enrichment will need to re-run. This means additional API calls (cost: ~$X)." |
| Highlights (toggle highlights) | `trip_final.json`, `output/` | "Outputs will need to be regenerated." |

The enrichment invalidation warning includes a cost estimate since vision API calls cost money. The Trip object in memory is reloaded from the earlier stage file after invalidation.

## Stage Model

The existing `config.py` defines: `["new", "ingest", "skeleton", "skeleton_reviewed", "enriched", "final", "generated"]`.

**New stage list:** `["new", "setup", "ingested", "reviewed", "enriched", "highlights_done", "generated"]`

| Old stage | New stage | Wizard step |
|-----------|-----------|-------------|
| `new` | `new` | (before wizard) |
| — | `setup` | 1. Setup (confirms inputs) |
| `ingest` + `skeleton` | `ingested` | 2. Ingest (consolidated) |
| `skeleton_reviewed` | `reviewed` | 3. Review |
| `enriched` | `enriched` | 4. Enrich |
| `final` | `highlights_done` | 5. Highlights |
| `generated` | `generated` | 6. Generate |

**Stage-to-file mapping** (for `SessionConfig.stage_file()`):

| Stage | File | Notes |
|-------|------|-------|
| `new` | — | No trip data yet |
| `setup` | — | Inputs configured but not processed |
| `ingested` | `trip_ingested.json` | Ingest + skeleton build run as one step. Raw ingest data (`trip_data.json`) is also written as an intermediate artifact for debugging but is not the stage file. |
| `reviewed` | `trip_reviewed.json` | After skeleton review + photo cull |
| `enriched` | `trip_enriched.json` | After vision API enrichment |
| `highlights_done` | `trip_final.json` | After highlight selection |
| `generated` | `trip_final.json` | Same file; outputs written to `output/` |

**Migration:** Sessions created under the old stage model are not migrated. The `start` command checks the session's stage format. If it uses old stages, it prints an error directing the user to delete the session and recreate it. No backward-compatible CLI resume path is maintained — old sessions must be deleted. This avoids complexity for a small number of in-progress sessions.

## Server Architecture

### Current State

`preview/server.py` creates a FastAPI app via `create_app(trip, save_fn)` — temporary, single-purpose.

### New Structure

Server becomes the long-lived session orchestrator.

#### App State

- Holds: `SessionConfig`, current `Trip` (None before ingest), current stage, reference to any running background task
- `create_app(session: SessionConfig)` — loads trip data based on `current_stage`
- Stage transitions update in-memory state and persist to disk

#### File Organization

```
src/post_trip_summary/
  server/
    __init__.py
    app.py            # FastAPI app factory, app state, lifecycle
    routes/
      wizard.py       # Wizard shell, stage navigation, setup/generate pages
      review.py       # Combined skeleton review + cull endpoints
      highlights.py   # Highlight picking endpoints
      progress.py     # SSE endpoint for compute stage progress
      api.py          # Session config, input management, description editing
  templates/
    wizard.html       # Base template with step indicator
    setup.html
    progress.html
    review.html       # Combined skeleton review + photo cull
    highlights.html
    generate.html
    # Existing output templates stay here:
    detailed_record.html
    shareable_summary.html
    blog_post.html
    # Existing review templates (deprecated, kept until preview command removed):
    photo_review.html
    skeleton_review.html
  preview/
    server.py         # Kept for backward compat (preview command), gradually deprecate
```

All templates stay in the existing `templates/` directory, sharing the same `PackageLoader("post_trip_summary", "templates")`. Wizard templates are new files alongside the existing ones. The thumbnail cache is attached to `app.state` rather than a module-level global.

#### API Endpoints

Carried over from existing server:
- `POST /api/skeleton/merge`
- `POST /api/skeleton/rename`
- `POST /api/skeleton/delete`
- `POST /api/skeleton/update-type`
- `POST /api/skeleton/add-note`
- `POST /api/skeleton/suggest-merge-name`
- `POST /api/toggle-keep`
- `POST /api/toggle-highlight`
- `POST /api/bulk-action`
- `GET /photos/{event_id}/{photo_idx}` (review UIs)
- `GET /photos/{filename}` (output preview templates)

New endpoints:
- `GET /api/progress` — SSE stream for compute stages
- `POST /api/update-description` — save edited event description
- `POST /api/session/inputs` — update input paths
- `POST /api/session/settings` — update vision provider settings
- `POST /api/generate` — trigger output generation with selected types
- `POST /api/stage/start` — kick off a compute stage (ingest or enrich)
- `GET /api/stage/current` — return current stage for wizard state

Preview endpoints (reused for Generate step previews):
- `GET /detailed`
- `GET /summary`
- `GET /blog`

#### Pipeline Function Changes

`ingest` functions, `build_skeleton`, `enrich_trip` gain an optional `progress_callback` parameter:
- When provided: called at each iteration with `(phase, current, total, label)`
- When not provided: functions behave exactly as today (backward compatible)
- The SSE endpoint reads from a thread-safe progress object that the callback writes to
