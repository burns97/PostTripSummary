# Montage-Based Enrichment Redesign

**Date:** 2026-04-08
**Status:** Draft

## Problem

The current enrichment pipeline sends 1-5 individual photos per event to Gemini and takes the first description returned. This produces narrow descriptions that capture one photo's content rather than the breadth of the event. A 53-photo visit to Hobbiton gets described as "a garden path with flowers" because the first photo happened to be of a minor feature.

The enrichment also takes ~25 minutes for a 129-event trip, with no option to trade speed for depth.

## Goals

1. Produce event descriptions that reflect the full scope of what was seen/done, not just one photo
2. Generate two levels of description: factual summary (always) and journal-style narrative (optional)
3. Offer quick and thorough modes so the user can choose speed vs. depth
4. Use Gemini's highlight picks from montages to improve photo selection
5. Stay within Gemini Flash free tier ($0 cost)

## Non-Goals

- Changing the skeleton building or clustering logic (addressed separately in photo scoring spec)
- Replacing the review UI for descriptions
- Supporting providers other than Gemini for montage analysis (Claude support can be added later)

## Design

### Montage Generation Utility

A shared utility (`src/post_trip_summary/vision/montage.py`) that takes a list of photos and produces a labeled grid image:

- Thumbnails arranged in a grid, each cell labeled with its index number (1, 2, 3...)
- Configurable parameters: `thumb_size` (default 256), `cols` (default 5), `max_count` (default 20)
- If more photos than `max_count`, pre-sample by temporal spread (first, evenly spaced, last) to capture the event arc
- Output as JPEG bytes ready to send to the vision provider
- PIL only (already a dependency), runs locally with no API cost

This utility is shared with the future montage-based photo scoring and cluster merge features from the photo scoring redesign spec.

### Enrichment Modes

Two modes selectable from the cost gate prompt and the headless API:

**Quick mode:**
- One montage per event, one Gemini call per event
- Prompt asks for a factual summary plus highlight picks (photo numbers from the grid)
- Result: `event.summary` = factual summary; `event.description` = same as summary
- Highlights marked from Gemini's picks
- Estimated: ~95-129 calls (events with photos), ~2-3 minutes on Gemini Flash

**Thorough mode:**
- Same montage call as quick mode (factual summary + highlight picks)
- Then send top 3-5 highlight photos individually at full resolution for detailed descriptions (landmark ID, sign reading, scene detail)
- Then a synthesis call combining the montage summary + individual descriptions into a journal-style narrative
- Result: `event.summary` = factual summary; `event.description` = narrative
- Estimated: ~129 montage + ~400 individual + ~80 synthesis = ~609 calls, ~15-20 minutes

Default is quick mode. Thorough mode available via cost gate choice or `--mode thorough` on CLI.

### Prompts

**Montage prompt (both modes):**
```
Here are {N} photos from a single event during a vacation trip, shown as a numbered grid.
{context: event name, location, time}

Describe what was seen and done across these photos. Focus on the overall experience,
not individual photos. 2-3 sentences, suitable for a trip summary.

Also pick the 5 most interesting/representative photos by their grid number.

Respond with JSON:
{"summary": "factual 2-3 sentence summary", "highlights": [3, 7, 12, 15, 19]}
```

**Individual photo prompt (thorough mode only):**
Uses the existing `scene` prompt — no changes needed.

**Narrative synthesis prompt (thorough mode only):**
```
Here is a factual summary of an event, plus detailed descriptions of key photos:

Summary: {montage summary}
Photo details:
1. {description}
2. {description}
...
{context: event name, location, time}

Write a 3-5 sentence journal-style narrative that brings this event to life.
Blend the overview with specific details from the photos.

Respond with JSON:
{"narrative": "journal-style paragraph"}
```

### Model Changes

**New field on Event dataclass:**
- `summary: str = ""` — factual summary from montage analysis (always populated after enrichment)

**Existing field behavior:**
- `description` — becomes the narrative in thorough mode; equals the summary in quick mode

**Serialization:** Both fields serialize automatically via the existing `__dict__`-based encoder. No changes needed to `serialization.py`.

### Data Flow

**Quick mode:**
1. Build montage for event (temporal spread if >20 photos)
2. Send montage + context to Gemini
3. `event.summary` = factual summary from response
4. `event.description` = same as summary
5. Mark highlights from Gemini's grid picks → `photo.is_highlight = True`

**Thorough mode:**
1. Build montage → Gemini → `event.summary`, mark highlights (same as quick)
2. Send individual highlight photos at full resolution → `photo.ai_description` on each
3. Synthesis call (text-only) → `event.description` = narrative

### Highlight Selection

Current `_select_highlights` uses temporal spread only. New behavior:
- If Gemini returned highlight picks from the montage, use those
- Fall back to quality-informed temporal spread (from photo scoring spec) if Gemini didn't pick, API unavailable, or event has <=3 photos

### Events with Few Photos (<=3)

No montage generated — send individual photos directly (similar to current behavior). The montage overhead isn't worthwhile for 1-3 photos. These events get individual descriptions and a summary synthesized from them if there are 2-3 photos.

### Cost Gate

Updated enrichment prompt:
```
=== Vision Enrichment ===
Provider: gemini (gemini-2.5-flash)
Events to analyze: 95 (with photos)

[q]uick — montage summaries only (~95 calls, ~2-3 min)
[t]horough — montages + detailed highlights + narrative (~600 calls, ~15-20 min)
[s]kip — highlights only, no AI descriptions
```

**Headless API:** `mode` parameter accepts `"quick"`, `"thorough"`, `"skip"` (replacing current `"full"`, `"reduced"`, `"skip"`).

### Fallback Behavior

- **No API key:** Select highlights by quality-informed temporal spread, no descriptions
- **Quota exhausted mid-run:** Keep whatever summaries/narratives were completed, fall back to highlight-only for remaining events
- **Montage generation fails** (e.g., all photos corrupt): Skip that event, log warning
- **API unavailable:** Same as no API key fallback

## File Changes

### New Files
- `src/post_trip_summary/vision/montage.py` — Montage grid generation utility
- `tests/test_montage.py` — Montage generation tests

### Modified Files
- `src/post_trip_summary/models.py` — Add `summary` field to Event
- `src/post_trip_summary/pipeline/enrich.py` — Replace per-photo analysis with montage-based flow, add quick/thorough modes
- `src/post_trip_summary/vision/prompts.py` — Add `montage` and `narrative_synthesis` prompt templates
- `src/post_trip_summary/vision/triage.py` — Update `plan_enrichment` for montage-based planning
- `src/post_trip_summary/vision/gemini.py` — Add montage analysis method (image + prompt, returns summary + highlights)
- `src/post_trip_summary/vision/client.py` — Add `analyze_montage` to VisionProvider ABC
- `src/post_trip_summary/server/compute.py` — Pass new mode values to enrichment
- `src/post_trip_summary/server/app.py` — Update cost gate options in headless API
- `src/post_trip_summary/cli.py` — Update CLI enrichment mode options

## Testing Strategy

- **Montage generation:** Unit test producing valid JPEG with correct dimensions, labels, configurable grid size, temporal sampling for >max_count photos
- **Quick mode:** Mock vision provider, verify montage sent, summary and highlights extracted correctly
- **Thorough mode:** Mock provider, verify montage → individual photos → synthesis flow
- **Few-photo events (<=3):** Verify individual photo path used instead of montage
- **Fallback:** Verify graceful degradation on quota exhaustion, missing API key, corrupt photos
- **Mode parameter:** Verify "quick", "thorough", "skip" all route correctly through headless and CLI paths
- **Backward compatibility:** Verify events with existing descriptions are preserved on re-run
