# Local Prefill Enrichment Design

**Date:** 2026-05-30
**Status:** Approved by delegation

## Problem

Cloud enrichment is still the final-quality path, but many photo descriptions can be drafted cheaply by a local multimodal model before any paid or quota-limited calls are made. The project needs an experimental way to front-load image description work with Ollama while keeping the result bounded enough for limited laptop hardware.

## Goals

1. Add an opt-in local prefill pass that writes draft `photo.ai_description` values.
2. Use only a small representative set per event by default.
3. Preserve existing human edits and cloud-generated descriptions unless explicitly overwritten.
4. Make the capability testable without contacting Ollama by accepting an injected provider.
5. Expose a CLI command that can run against reviewed or enriched trip data.

## Non-Goals

- No automatic cloud-vs-local quality arbitration.
- No background scheduling or parallel model calls.
- No new persisted cache format.
- No change to the default wizard enrichment mode.

## Architecture

Create `post_trip_summary.pipeline.local_prefill` with a single high-level function:

```python
prefill_trip_with_local_descriptions(
    trip,
    provider=None,
    max_photos_per_event=2,
    overwrite=False,
    progress_callback=None,
) -> LocalPrefillStats
```

When no provider is injected, the function creates an Ollama provider from the `ollama_*` settings added by the provider PR. It iterates events with kept photos, chooses representatives with the existing `select_representatives()` helper, calls the provider with the existing `scene` prompt and event context, and stores successful descriptions on photos.

The pass writes a light event summary only when the event lacks one. If multiple local descriptions are available, it uses local text synthesis through the provider; otherwise it uses the first photo description. Existing event descriptions are left alone unless `overwrite=True`.

Add a CLI command:

```bash
post-trip-summary local-prefill <slug> --max-photos-per-event 2
```

It loads `reviewed` data when available, or `enriched` data for reruns. It saves back to the same stage file and does not advance the session stage.

## Data Flow

1. User completes skeleton review.
2. User runs local prefill with Ollama running.
3. The pass fills draft photo descriptions and sparse event summaries for representative photos.
4. User can inspect descriptions in the normal review/highlight flows.
5. Later Gemini enrichment can still run for higher-quality summaries.

## Error Handling

- Provider exceptions are counted as failures and do not abort the entire trip.
- Missing or unreadable image files are counted as failures.
- Existing descriptions are skipped by default.
- If no events or no kept photos exist, the pass returns zero counts without error.

## Testing

- Unit-test representative photo selection, skip behavior, overwrite behavior, and summary population with fake providers.
- Unit-test provider construction uses Ollama settings when no provider is injected.
- CLI-test reviewed-stage and enriched-stage save behavior with the prefill function patched.

## Validation

This design adds a reversible, opt-in pre-processing tool. It keeps local-model experimentation away from default enrichment while creating useful local artifacts that can reduce manual review effort and inform later cloud calls.
