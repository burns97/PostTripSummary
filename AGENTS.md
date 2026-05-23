# Post-Trip Summary

A CLI tool that generates trip summaries from vacation photos and supplementary travel data (itineraries, credit card statements, Google Maps timeline, Apple Health, Day One journals).

## Quick Reference

- **Language:** Python 3.10+
- **Package manager:** pip/setuptools (editable install: `pip install -e .`)
- **CLI entry point:** `post-trip-summary` (defined in `src/post_trip_summary/cli.py`)
- **Run tests:** `python -m pytest` (or target specific files: `python -m pytest tests/test_skeleton.py -v`)
- **Test config:** `pyproject.toml` (`[tool.pytest.ini_options]`, testpaths=tests, pythonpath=src)

## Architecture

### Pipeline Stages (sequential, resumable via `post-trip-summary resume <slug>`)

1. **Ingest** — Parse photos (EXIF/GPS), Excel itinerary, credit card CSV, Google Maps JSON, Apple Health XML, Day One JSON
2. **Skeleton** — Cluster photos by time+GPS, reverse geocode centroids (Nominatim), cross-reference with supplementary data, build Day/Event timeline
3. **Review Skeleton** — Interactive CLI review of auto-generated skeleton
4. **Enrich** — Montage-based vision analysis (Gemini). Quick mode: one montage per event for factual summaries. Thorough mode: montages + individual highlight descriptions + journal-style narratives.
5. **Review Details** — Interactive detail review
6. **Generate** — Output detailed record HTML, shareable PDF, blog post, photo prep

### Key Design Principles

- **Photos are the primary data source.** Timestamps and GPS from EXIF drive clustering and event creation.
- **Reverse geocoding produces event names.** Nominatim POI fields (tourism, amenity, leisure, historic, shop, natural) are preferred over city/area names. Supplementary data enriches (event type, sources) but does not override geo-based POI names.
- **Name resolution priority:** Google Maps > geo POI > itinerary > Day One > geo area. Expenses never set the event name.
- **Vision API calls cost money.** Always estimate cost before making API calls. This is a hobby project — minimize costs.

### Source Layout

```
src/post_trip_summary/
  cli.py              # Click CLI with resume/preview/generate commands
  models.py           # Dataclasses: Trip, Day, Event, Photo, Location, etc.
  config.py           # Session management (create/load/save)
  serialization.py    # JSON serialization for Trip model
  settings.py         # Global settings (vision provider, models)
  geo/
    clustering.py     # Photo clustering by time gap + GPS distance
    interpolate.py    # GPS interpolation for photos missing coordinates
    reverse_geocode.py # Nominatim reverse geocoding with LRU cache
  pipeline/
    ingest/           # One module per data source (photos, excel, credit_card, etc.)
    skeleton.py       # Build trip skeleton from clusters + supplementary data
    enrich.py         # Vision API enrichment
    review_skeleton.py
    review_details.py
  vision/
    client.py         # Vision provider abstraction (Codex, Gemini)
    gemini.py         # Gemini vision provider
    montage.py        # Thumbnail grid generation for montage-based analysis
    triage.py         # Photo dedup and highlight selection
    prompts.py        # Vision prompt templates
  output/             # Generators: detailed_record, shareable_pdf, blog_post, photo_prep
  preview/
    server.py         # FastAPI preview server
```

### Models (models.py)

All models are plain dataclasses — no ORM, no Pydantic. Key types: `Trip`, `Day`, `Event`, `Photo`, `Location`, `Accommodation`, `Transit`, `Expense`.

### External Services

- **Reverse geocoding** (geopy): LocationIQ (2 req/sec, free 5K/day) if API key configured, otherwise Nominatim (1 req/sec). Auto-fallback to Nominatim on LocationIQ failure. Results cached in SQLite at `~/.post-trip-summary/geocache.db`.
- **Overpass API** (OSM): Supplementary POI radius search when geocoder returns no POI name. Finds nearby tourism/amenity/historic/leisure features. Free, no API key.
- **Vision APIs** (Gemini/Codex): Photo description for enrichment. Pluggable provider via settings. Cost-gated.
- Geocache is SQLite; session state is JSON files on disk.

## Conventions

- Tests live in `tests/test_*.py`, one per module. Use `pytest` (no unittest).
- Test helpers (like `_photo()`, `_make_cluster()`) are defined at the top of each test file, not in a shared conftest.
- Pure functions (like `_build_geo_result`) are tested without mocking. Integration tests that hit Nominatim are acceptable for reverse geocoding (small, cached).
- Commit messages: short imperative summary. No conventional-commit prefix required but `feat:`, `fix:` are fine.
- Branch: `develop` is the main branch.
