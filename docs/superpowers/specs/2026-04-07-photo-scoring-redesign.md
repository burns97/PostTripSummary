# Photo Scoring Redesign: Quality-Informed Selection + Montage-Based AI

**Date:** 2026-04-07
**Status:** Draft

## Problem

The current quality scoring pass during ingest (~1-2 min for 500 photos) computes sharpness, colorfulness, and exposure scores but they are only used for culling the bottom 15%. The scores are never used for photo selection — `select_representatives` and `_select_highlights` both use pure temporal spread, picking evenly spaced photos regardless of quality. Since the user typically pre-curates their photos before processing, the culling is mostly redundant. The selection logic doesn't pick the "right" photos — it has no understanding of content or quality.

Additionally, time+GPS clustering sometimes splits events that are clearly the same place/activity (e.g., a long lunch with a GPS gap, or re-visiting a spot after a short walk). These splits can't be fixed by heuristics alone.

## Goals

1. Make quality scores influence photo selection, not just culling
2. Use AI vision (via thumbnail montages) to make smarter clustering and selection decisions
3. Hide the scoring wait time by running it concurrently with other ingest work
4. Cache quality scores so re-runs are near-instant
5. Keep API costs at $0 (Gemini Flash free tier) and show estimates before making calls

## Non-Goals

- Changing the scoring algorithm itself (sharpness/colorfulness/exposure weights stay as-is)
- Replacing the existing enrichment pipeline (Stage 4) — this augments skeleton building (Stage 2)
- CLIP or ML-based local scoring (too heavy for a hobby project)

## Design

### Part 1: Quality-Informed Selection (Quick Win)

#### Selection Algorithm Change

`select_representatives` and `_select_highlights` currently pick N photos by evenly spacing indices across a time-sorted list. The new approach:

1. Sort candidates by timestamp
2. Divide into N time buckets (where N = desired count)
3. Within each bucket, pick the photo with the highest `quality_score`

Photos without a quality score (e.g., scoring was skipped or cache miss on a new photo) receive a neutral default of 50 so they are never unfairly penalized or preferred.

This preserves temporal coverage while preferring technically better photos within each time window.

#### Background Scoring

Move `score_photos` to run in a background thread during ingest, after EXIF extraction but concurrent with supplementary data ingestion (Excel, credit card, Maps, Day One, etc.). The scores only need to be ready by the time selection functions are called during skeleton building or enrichment.

This hides the ~1-2 minute wait behind work that's already happening. If scoring hasn't finished by the time it's needed, wait for the thread to complete (graceful join).

#### Quality Score Cache

SQLite database at `~/.post-trip-summary/quality_cache.db`.

**Schema:**
```sql
CREATE TABLE quality_scores (
    file_hash TEXT PRIMARY KEY,   -- SHA-256 of first 64KB
    quality_score REAL,
    sharpness REAL,
    colorfulness REAL,
    exposure REAL,
    scored_at TEXT                 -- ISO timestamp
);
```

- **Key:** SHA-256 of the first 64KB of the file. Fast to compute, sufficient to uniquely identify a photo without reading multi-MB files.
- **Value:** Composite score plus individual components. Storing components allows re-weighting without re-scoring.
- **On cache hit:** Skip PIL/scipy entirely, assign scores directly.
- **On cache miss:** Score normally, write to cache.
- **No TTL/expiration:** Photo quality scores don't change. Cache grows monotonically but stays tiny (one row per unique photo ever processed).

### Part 2: Montage-Based AI Selection + Cluster Merging

#### Montage Generation Utility

A function that takes a list of photos and produces a labeled grid image:

- Thumbnails resized to 256x256, arranged in a grid (e.g., 4x5 for 20 photos)
- Each cell labeled with its index number (1, 2, 3...) so the AI can reference specific photos by number
- Output as JPEG bytes ready to send to the vision provider
- Max grid size: 20 photos (4x5). If more than 20, pre-sample by temporal spread before building the grid.
- Uses PIL only (already a dependency).

#### Cluster Merge Suggestions (Stage 2, after clustering, before reverse geocoding)

1. **Identify borderline pairs:** Two temporally adjacent clusters where:
   - The time gap is within 2x the normal split threshold, OR
   - GPS centroids are within 500m despite exceeding the time threshold
2. **Build a combined montage** of both clusters, labeled "Group A: 1-N, Group B: (N+1)-M"
3. **Ask Gemini Flash:** Single-image prompt requesting JSON response:
   ```
   These photos were split into two groups by time/location.
   Group A: photos 1-{N}
   Group B: photos {N+1}-{M}
   Do they appear to be the same place or activity?
   Respond with JSON: {"merge": true/false, "reason": "brief explanation"}
   ```
4. **Apply merges** to the cluster list before proceeding to reverse geocoding and event creation.

**Estimated calls:** For a 500-photo trip with 40-60 clusters, approximately 5-15 borderline pairs. Well within Gemini Flash free tier (1,500 req/day).

#### AI-Driven Highlight Selection (Stage 2, after clusters are finalized)

1. For each event with >5 kept photos, build a numbered montage of all kept photos (up to 20).
2. **Ask Gemini Flash:**
   ```
   Here are {N} photos from a single event during a vacation trip.
   Pick the 5 most interesting and representative photos for a trip journal.
   Consider: landmarks, people, activities, scenic views, unique moments.
   Avoid: duplicates, blurry shots, photos of the ground or ceiling.
   Respond with JSON: {"picks": [3, 7, 11, 2, 15]}
   ```
3. Mark the picked photos as `is_highlight = True`.
4. Events with <=5 kept photos skip this — all photos are highlights by default.

**Estimated calls:** For a typical trip, 15-25 events have >5 photos. So 15-25 additional calls.

#### Cost Gate

Before making any montage API calls during skeleton building, show the user an estimate:

```
=== AI-Assisted Clustering ===
Provider: gemini (gemini-2.5-flash)
Cluster merge checks: ~12 calls
Highlight selection: ~20 calls
Estimated cost: Free (Gemini Flash free tier)

[a]pprove / [s]kip AI assistance
```

Consistent with the existing cost-gate pattern in enrichment.

The headless (server) path uses a parameter to control this (default: approve if free tier).

#### Total API Budget

For a typical 500-photo, 10-day trip:
- Cluster merging: ~5-15 calls
- Highlight selection: ~15-25 calls
- **Total: ~20-40 Gemini Flash calls** added to skeleton building
- Free tier allows 1,500 requests/day — this uses ~2% of the daily budget

#### Fallback Behavior

If the vision API is unavailable (no API key, quota exhausted, or user skips):
- No cluster merging — keep the heuristic clusters as-is
- Highlight selection falls back to quality-informed temporal spread (Part 1)
- The pipeline continues normally with no degradation beyond the missing AI input

## File Changes

### New Files
- `src/post_trip_summary/vision/montage.py` — Montage grid generation utility
- `src/post_trip_summary/pipeline/quality_cache.py` — SQLite quality score cache
- `tests/test_montage.py` — Montage generation tests
- `tests/test_quality_cache.py` — Cache read/write tests

### Modified Files
- `src/post_trip_summary/vision/triage.py` — Update `select_representatives` to use quality-informed bucket selection
- `src/post_trip_summary/pipeline/enrich.py` — Update `_select_highlights` to use quality-informed bucket selection
- `src/post_trip_summary/pipeline/quality.py` — Integrate cache reads/writes into `score_photos`
- `src/post_trip_summary/server/compute.py` — Run scoring in background thread; add montage-based merge and highlight selection to skeleton building
- `src/post_trip_summary/pipeline/skeleton.py` — Accept and apply cluster merge suggestions
- `src/post_trip_summary/vision/prompts.py` — Add `merge_check` and `highlight_pick` prompt templates
- `src/post_trip_summary/cli.py` — Add cost gate for AI-assisted clustering in CLI path

## Testing Strategy

- **Quality cache:** Unit tests for cache hit/miss, hash computation, schema creation
- **Quality-informed selection:** Unit tests verifying higher-quality photos are preferred within time buckets, neutral default for unscored photos
- **Montage generation:** Unit test that produces a valid JPEG grid with correct dimensions and labels
- **Cluster merging:** Unit test with mock vision provider, verifying merge logic for borderline pairs and no-op for non-borderline pairs
- **AI highlight selection:** Unit test with mock provider, verifying picked indices are marked as highlights
- **Fallback:** Test that missing API key / quota exhaustion gracefully falls back to Part 1 behavior
- **Integration:** End-to-end test of skeleton building with montage features enabled (mock API)
