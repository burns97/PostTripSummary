# Feature: Vision API Response Cache

## Context

Vision API calls (Gemini/Claude) are the most expensive part of the pipeline — they cost real money and take time. Currently, every re-run of enrichment re-calls the API for every photo, even if nothing changed. During iterative testing of the same trip, this wastes money and time on identical requests.

**Goal:** Cache vision API responses in SQLite so identical requests return cached results instantly.

## Design

### Cache Key

Five columns form the composite key — if any differ, it's a cache miss:

| Column | Why |
|--------|-----|
| `photo_path` | Which photo (or prompt text for synthesize calls) |
| `purpose` | "landmark", "sign", "scene", "synthesize" — determines the prompt |
| `context` | Metadata string (timestamp, city, POI name) — changes if skeleton changes |
| `provider` | "gemini" or "claude" — different models give different results |
| `model` | e.g. "gemini-2.5-flash" — model upgrades should invalidate cache |

### Cache Value

Columns matching `VisionResult` dataclass (`src/post_trip_summary/vision/client.py:9-14`):
- `description` (TEXT)
- `landmark` (TEXT, nullable)
- `text_found` (TEXT, nullable)
- `confidence` (TEXT)
- `created_at` (TEXT, ISO UTC)

### Implementation

**New file:** `src/post_trip_summary/vision/cache.py`
- `VisionCache` class following the `GeoCache` pattern (`src/post_trip_summary/geo/cache.py`)
- SQLite at `~/.post-trip-summary/visioncache.db`
- Methods: `get(photo_path, purpose, context, provider, model) -> VisionResult | None`, `put(...)`, `clear()`, `__len__()`

**Modify:** `src/post_trip_summary/vision/client.py`
- In `ClaudeProvider.analyze()`: check cache before API call, store result after
- Same for `GeminiProvider.analyze()` in `src/post_trip_summary/vision/gemini.py`
- Or: wrap at the `enrich_trip()` level in `src/post_trip_summary/pipeline/enrich.py` (simpler — single integration point)

**Recommended integration point:** `enrich.py` lines 135-166 (Pass 1 per-photo analysis loop). Before calling `provider.analyze()`, check cache. After successful call, store in cache. This keeps the provider classes unchanged.

### Synthesize calls

Synthesis prompts (`purpose="synthesize"`) don't have a photo — they blend multiple photo descriptions into one event summary. Cache key would use the prompt text hash instead of photo_path.

## Files to Change

| File | Action |
|------|--------|
| `src/post_trip_summary/vision/cache.py` | NEW — VisionCache class |
| `src/post_trip_summary/pipeline/enrich.py` | MODIFY — add cache lookup/store around API calls |
| `tests/test_vision_cache.py` | NEW — cache roundtrip tests |

## Verification

1. `python -m pytest tests/test_vision_cache.py -v` — cache logic works
2. Run enrichment on a trip — verify `~/.post-trip-summary/visioncache.db` is populated
3. Re-run enrichment on same trip — verify zero API calls (all cache hits), completes in seconds
4. Change an event's location in skeleton review — verify that event's photos get re-enriched (cache miss due to changed context)
