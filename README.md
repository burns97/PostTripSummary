# Post-Trip Summary

Generate rich trip summaries from vacation photos and travel data. Feed in your photos, spreadsheets, credit card statements, Google Maps timeline, Apple Health exports, and Day One journals — get back a detailed record, shareable PDF, and blog post.

## Installation

Requires Python 3.10+.

```bash
python -m venv .venv

# Activate the virtual environment
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -e .
```

### System dependencies

- [ExifTool](https://exiftool.org/) must be installed and on your PATH (used for photo metadata extraction)
- [WeasyPrint](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) requires system libraries for PDF generation — see their docs for platform-specific instructions

### Vision provider setup

The enrichment stage uses an AI vision API to describe photos and identify landmarks. Two providers are supported: **Google Gemini** (default, free tier) and **Claude** (paid).

#### Google Gemini (default)

1. Go to [Google AI Studio](https://aistudio.google.com/apikey) and create an API key
2. Set it as an environment variable or in the settings file:

```bash
# macOS / Linux
export GOOGLE_API_KEY=AIza...

# Windows (PowerShell)
$env:GOOGLE_API_KEY = "AIza..."
```

Gemini Flash is free for moderate usage, so the pipeline will show "Free" at the cost gate.

#### Claude (alternative)

To use Claude's vision API instead, get an API key from [console.anthropic.com](https://console.anthropic.com/) and configure it:

```bash
# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-...

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Then switch the provider in settings (see below).

#### Settings file

Global settings live at `~/.post-trip-summary/settings.toml`. Run `post-trip-summary config` to view or edit. The file is auto-created on first use with these defaults:

```toml
[vision]
provider = "gemini"           # "gemini" or "claude"

gemini_api_key = ""           # or set GOOGLE_API_KEY env var
gemini_model = "gemini-2.0-flash"

claude_api_key = ""           # or set ANTHROPIC_API_KEY env var
claude_model = "claude-sonnet-4-20250514"
```

API keys can be set either in this file or via environment variables. Environment variables are used as a fallback when the settings file value is empty.

The pipeline will show a cost estimate and ask for approval before making any API calls.

## Quick start

```bash
# Create a new trip session
post-trip-summary new "Iceland 2025"

# Add data sources
post-trip-summary add-input iceland-2025 \
  --photos ~/Photos/Iceland \
  --excel ~/Documents/iceland-itinerary.xlsx \
  --credit-card ~/Downloads/cc-statement.csv \
  --google-maps ~/Downloads/Semantic-Location-History/ \
  --apple-health ~/Downloads/export.xml \
  --dayone ~/Downloads/DayOne.json

# Run the pipeline (ingest → skeleton → review → enrich → review)
post-trip-summary resume iceland-2025

# Preview in browser
post-trip-summary preview iceland-2025

# Generate final outputs
post-trip-summary generate iceland-2025
```

## Pipeline stages

The pipeline runs in stages, saving progress after each step so you can resume at any point:

| Stage | Description |
|-------|-------------|
| **Ingest** | Reads photos (EXIF/GPS), Excel itineraries, credit card CSVs, Google Maps timeline, Apple Health, and Day One journals. Scores photo quality and auto-culls the bottom percentile. |
| **Skeleton** | Clusters events by time and location into a day-by-day trip structure, reverse geocodes centroids via Nominatim |
| **Review skeleton** | Review and edit events in browser or CLI — merge, rename, delete, change type, add notes (browser UI opens by default) |
| **Cull photos** | Optional browser-based photo review to remove unwanted shots before enrichment |
| **Enrich** | Uses AI vision (Gemini or Claude) to describe photos and identify landmarks (with cost estimation and approval) |
| **Pick highlights** | Optional browser-based selection of highlight photos for summary outputs |
| **Review details** | Final interactive review of descriptions and details |
| **Generate** | Produces output files: detailed HTML record, shareable PDF, blog post, and a route map |

### Restarting from a stage

Use `--from` to jump back to an earlier stage without re-running everything before it:

```bash
# Rebuild skeleton without re-ingesting (useful after changing clustering settings)
post-trip-summary resume iceland-2025 --from skeleton

# Re-run enrichment without rebuilding skeleton
post-trip-summary resume iceland-2025 --from enriched
```

Valid values: `ingest`, `skeleton`, `skeleton_reviewed`, `enriched`.

## Browser-based review

Several pipeline stages offer browser-based UIs (powered by FastAPI + Jinja2) as an alternative to the CLI:

- **Skeleton review** (`/review/skeleton`) — Visual event editor with photo thumbnails. Checkbox-select events to merge, click names to rename inline, delete events, change types, and add notes.
- **Photo cull** (`/review/cull`) — Toggle keep/remove on individual photos with quality score badges. Bulk actions per event.
- **Highlight picker** (`/review/highlights`) — Select highlight photos for summary outputs.

These can also be launched standalone:

```bash
post-trip-summary review-skeleton iceland-2025
post-trip-summary cull-photos iceland-2025
post-trip-summary pick-highlights iceland-2025
```

## Supported inputs

- **Photos** — JPEG, PNG, HEIC/HEIF, TIFF, WebP (reads EXIF timestamps and GPS coordinates)
- **Excel spreadsheet** — Itinerary with accommodations, transits, and activities
- **Credit card CSV** — Transaction history for expense tracking
- **Google Maps Timeline** — Semantic Location History JSON for place visits and travel segments
- **Apple Health** — Workout and step data export
- **Day One** — Journal entries export

## Outputs

- **Detailed record** — Full HTML document with every event, photo, and note
- **Shareable PDF** — A summary with route map suitable for sharing
- **Blog post** — HTML formatted for publishing
- **Photo prep** — Organized and selected highlight photos

## CLI reference

```
post-trip-summary new <name>              Create a new trip session
post-trip-summary list                    List all sessions
post-trip-summary add-input <slug> ...    Add data sources to a session
post-trip-summary resume <slug>           Resume pipeline from last stage
post-trip-summary resume <slug> --from <stage>  Restart from a specific stage
post-trip-summary preview <slug>          Preview trip in browser (FastAPI)
post-trip-summary generate <slug>         Generate final output files
post-trip-summary config                  View/edit global settings
post-trip-summary delete <slug>           Delete a session
post-trip-summary review-skeleton <slug>  Review skeleton in browser (standalone)
post-trip-summary cull-photos <slug>      Cull photos in browser (standalone)
post-trip-summary pick-highlights <slug>  Pick highlights in browser (standalone)
```

## Project structure

```
src/post_trip_summary/
├── cli.py                  # Click CLI entry point
├── config.py               # Session management
├── settings.py             # Global settings (vision provider, API keys)
├── models.py               # Core data models (Trip, Day, Event, Photo, etc.)
├── serialization.py        # JSON serialization/deserialization
├── geo/
│   ├── clustering.py       # Photo clustering by time gap + GPS distance
│   ├── interpolate.py      # GPS interpolation for photos missing coordinates
│   └── reverse_geocode.py  # Nominatim reverse geocoding with LRU cache
├── pipeline/
│   ├── ingest/             # Data source parsers (photos, excel, credit card, etc.)
│   ├── skeleton.py         # Build day-by-day trip structure from clusters
│   ├── skeleton_ops.py     # Skeleton editing operations (merge, rename, delete, etc.)
│   ├── quality.py          # Photo quality scoring and auto-cull
│   ├── review_skeleton.py  # Interactive skeleton review (CLI fallback)
│   ├── review_details.py   # Interactive detail review
│   └── enrich.py           # Vision API enrichment with cost gate
├── vision/
│   ├── client.py           # Abstract VisionProvider + Claude implementation
│   ├── gemini.py           # Gemini vision provider
│   ├── triage.py           # Photo dedup and highlight selection
│   └── prompts.py          # Vision prompt templates
├── output/
│   ├── detailed_record.py  # Full HTML record generation
│   ├── shareable_pdf.py    # Summary PDF with route map
│   ├── blog_post.py        # Blog HTML output
│   └── photo_prep.py       # Highlight photo organization
├── preview/
│   └── server.py           # FastAPI preview + review server
└── templates/
    ├── detailed_record.html
    ├── shareable_summary.html
    ├── blog_post.html
    ├── photo_review.html      # Cull / highlights browser UI
    └── skeleton_review.html   # Skeleton review browser UI
```

## Session data

Sessions are stored in `~/.post-trip-summary/sessions/<slug>/` and contain config, intermediate pipeline data, and generated outputs. Each stage writes its own JSON file so you can safely re-run from any point.
