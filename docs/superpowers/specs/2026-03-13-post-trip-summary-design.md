# Post-Trip Summary — Design Spec

## Overview

A Python CLI tool that processes vacation photos and supplementary trip data to produce a detailed personal trip record and a shareable summary for friends and family. The tool works interactively, building a trip timeline in stages and asking for user confirmation at each step — similar to how Claude Code operates.

## Problem

After a vacation with 1,000–5,000 photos across multiple devices, reconstructing a coherent narrative of where you went, when, and what you did is tedious. Photos sit in folders sorted by date with no context. Trip planning documents, credit card statements, and journal entries hold valuable information but are scattered across formats. Assembling all of this into something meaningful — whether for personal reference or to share with others — takes significant manual effort.

## Goals

- Automatically reconstruct a trip timeline from photos (EXIF/GPS) and supplementary data sources
- Identify landmarks, restaurants, and points of interest through AI vision and cross-referencing
- Produce a detailed personal record (comprehensive, information-focused)
- Produce a shareable summary (curated highlights, 3-5 pages)
- Minimize cost of external API usage through smart photo triage
- Support an interactive, staged workflow where the user reviews and guides output at each step

## Non-Goals (V1)

- Interactive map/timeline (V2)
- Photo book layout suggestions (V2)
- YouTube-style video generation (V2)
- Standalone expense report (expense data is included in the detailed record, pulled from existing spreadsheet)
- Real-time trip tracking (this is a post-trip tool)

## Data Inputs

### Primary

- **Photo directory** — iPhone photos with EXIF data (GPS, timestamps). Supported formats: JPG, JPEG, PNG, HEIC, HEIF, TIFF, WEBP
- **Excel workbook** — Trip itinerary with tabs for accommodations, flights, activities, and expenses

### Secondary (optional, any combination)

- **Credit card CSV** — Transaction exports with dates, amounts, merchant names
- **Google Maps Timeline** — JSON export from Google Takeout with visited places and routes
- **Apple Health export** — XML export with workout GPS tracks (walks, hikes)
- **Day One journal export** — JSON export with text entries and associated photos

### Additional Input Suggestions

These data sources were considered and may be added in future versions if the user finds them valuable:

- Fitness tracker detailed route data (beyond Apple Health)
- Travel app data (TripIt, airline apps)
- Booking confirmation emails (parsed for hotel/restaurant details)

## Architecture

### Pipeline Stages

The system processes data through 6 sequential stages. Each stage reads from the previous stage's output and writes its own. All intermediate state is persisted to JSON so the user can stop, resume, and re-run any stage.

#### Stage 1: Ingest & Extract

Scan all input sources and extract structured data.

- **Photos**: Walk the directory, extract EXIF metadata using PyExifTool (GPS coordinates, timestamps, camera info). Use MediaMover's date resolution cascade as a pattern: try `DateTimeOriginal` → `CreateDate` → `GPSDateTime` → filename pattern → folder name.
- **Excel workbook**: Parse each tab using openpyxl. Extract accommodations (name, address, dates), transit (mode, departure/arrival, times), and planned activities (name, location, date/time).
- **Credit card CSV**: Parse and normalize transactions. Extract date, amount, merchant name, and (if available) merchant category.
- **Google Maps Timeline**: Parse JSON from Google Takeout. Extract place visits (name, address, time range) and activity segments (routes between places).
- **Apple Health**: Parse XML export. Extract workout routes with GPS tracks, timestamps, distance, and duration.
- **Day One**: Parse JSON export. Extract journal entries with text, timestamps, and associated photo references.

Output: `trip_data.json` — all raw extracted data with normalized timestamps.

#### Stage 2: Build Skeleton

Construct an ordered timeline of trip events.

- Establish trip date range from itinerary or photo timestamp boundaries
- **Photo clustering**: Group photos into "stops" using:
  - Time proximity: photos within ~15 minutes (configurable in `config.json` as `cluster_time_gap_minutes`)
  - GPS proximity: photos within ~200 meters (configurable in `config.json` as `cluster_distance_meters`)
  - Cluster merging: adjacent clusters that overlap geographically are merged (walking around a large site)
- **Reverse geocoding**: Convert GPS coordinates to place names using `reverse_geocoder` (offline, free). Provides city/town level; combined with itinerary data for street-level detail.
- **Cross-referencing**: Match clusters against:
  - Itinerary events (planned hotel matches cluster near that address)
  - Credit card transactions (charge at 12:30 PM near a photo cluster = lunch stop)
  - Google Maps Timeline visits (confirmed place name and time)
  - Apple Health workouts (walking route overlapping photo clusters)
  - Day One entries (journal text matching event timeframe)
- **Event classification**: Label each event as landmark, restaurant, hotel, activity, transit, or unknown based on available signals
- **Structural note**: `Trip.accommodations` and `Trip.transits` are the canonical records (parsed from the itinerary). When they appear in the day-by-day timeline, they are represented as `Event` entries with `type="hotel"` or `type="transit"` that reference back to the canonical record. This avoids duplication while allowing them to appear naturally in the chronological flow.

Output: `trip_skeleton.json` — ordered timeline of events with time ranges, locations, and confidence sources.

#### Stage 3: Interactive Skeleton Review

Present the skeleton day-by-day in the terminal. The user confirms, corrects, or edits:

```
── Day 1: March 5 (Paris) ──────────────
 1. ✈ Arrival CDG         2:00 PM
 2. 🏨 Hotel Le Marais     3:30 PM    (matched: itinerary)
 3. 📍 Eiffel Tower area   4:15-6:00 PM  (147 photos, GPS cluster)
 4. 🍽 Unknown restaurant  7:30 PM    (credit card: €87.50 "REST LE PETIT")

Does this look right? [y/edit/skip]
```

User actions: confirm a day, rename/merge/split events, adjust times, add missing events, add notes, skip to revisit later.

Output: `trip_skeleton_reviewed.json` — user-approved timeline.

#### Stage 4: Enrich

Send representative photos to Claude Vision API for detailed identification.

- **Photo triage** (see Photo Intelligence section): Select 2-5 representative photos per event, skipping events already confidently identified (confidence = confirmed by 2+ independent sources, e.g., itinerary + GPS match, or credit card + GPS proximity)
- **Cost estimation**: Before any API calls, display estimated cost and get user approval. If the user declines, they can choose to: (a) skip enrichment entirely and proceed to output with skeleton data only, (b) reduce scope by selecting specific days or events to enrich, or (c) adjust the budget ceiling and let the tool prioritize the most uncertain events first
- **Vision analysis**: Targeted prompts per purpose:
  - Landmark identification: "Identify the landmark or notable location in this photo"
  - Sign/text reading: "Read any visible text, signs, or menus in this photo"
  - Scene description: "Describe this scene briefly for a trip journal"
- **Journal matching**: Associate Day One entries with events by timestamp proximity
- **Photo selection**: For each event, select the best highlight photos based on variety, quality heuristics (not blurry, good composition), and content coverage

Output: `trip_enriched.json` — events with AI descriptions, landmark names, selected highlight photos.

#### Stage 5: Interactive Detail Review

Present enriched details event-by-event:

```
── Eiffel Tower (4:15-6:00 PM) ──────────
Landmark: Eiffel Tower, confirmed from Trocadéro viewpoint
Photos: 147 total, 4 selected as highlights
  [1] Family selfie with tower          ★ highlight
  [2] Tower from Trocadéro gardens      ★ highlight
  [3] Close-up iron lattice detail      ★ highlight
  [4] Sunset view from Champ de Mars    ★ highlight

Accept these selections? [y/edit/add note]
```

User can override photo selections, edit descriptions, add personal notes.

Output: `trip_final.json` — fully reviewed and approved trip data.

#### Stage 6: Generate Outputs

Produce final deliverables from the approved `trip_final.json`.

- **Photo preparation**: Resize highlight photos to web-appropriate dimensions (max 1920px wide) and copy to `output/photos/`. Originals are not modified.
- **Detailed record**: Render `trip_final.json` through a Jinja2 HTML template. Each day becomes a section with events, photos (referenced from `photos/`), descriptions, and notes. CSS is embedded inline for portability.
- **Shareable PDF**: Render a separate Jinja2 template focused on highlights only. Convert to PDF using WeasyPrint. The template uses print-friendly CSS (page breaks, margins).
- **Blog HTML** (optional): Render a third template producing clean HTML suitable for pasting into a blog editor. Images are referenced, not embedded.
- **Preview server**: Before final generation, `post-trip-summary preview` launches a local FastAPI server that renders the same templates with live data, allowing the user to review in-browser and request changes via the terminal. Once satisfied, `post-trip-summary generate` writes the final files to the output directory.

Output: `output/` directory containing `detailed-record.html`, `photos/`, `shareable-summary.pdf`, and optionally `blog-post.html`.

### Photo Intelligence

#### Clustering Algorithm

1. Sort all photos by timestamp
2. Walk sequentially; start a new cluster when gap exceeds time threshold (~15 min)
3. Within each time cluster, sub-cluster by GPS proximity (~200 meters)
4. Merge adjacent clusters that overlap geographically (handles large venues visited over extended time)
5. Assign each cluster a centroid (average GPS) and time range

#### Smart Triage for Vision API

Not every photo needs AI analysis. The triage pipeline minimizes API cost:

1. **Skip known contexts**: If a cluster maps confidently to an itinerary event (hotel address at check-in time), skip vision for identification. May still send 1 photo for scene description.
2. **Perceptual deduplication**: Use `imagehash` (average hash, same as MediaMover) to identify near-identical shots within a cluster. Only send unique compositions.
3. **Representative selection**: From each cluster, pick candidates prioritizing:
   - Variety of content (different angles/subjects)
   - Photos likely containing signs/text (heuristic: building-facing, landscape orientation)
   - Quality indicators (not obviously blurry based on EXIF data like shutter speed)
4. **Batch by purpose**: Separate prompts for landmark ID, sign reading, and scene description — targeted prompts get better results.
5. **Cost gate**: Present total estimate before execution. User approves or adjusts scope.

Target: ~100-150 API calls for a 3,000-photo trip.

## Data Models

```python
@dataclass
class Trip:
    name: str
    date_range: tuple[date, date]
    days: list[Day]
    accommodations: list[Accommodation]
    transits: list[Transit]
    expenses: list[Expense]

@dataclass
class Day:
    date: date
    events: list[Event]

@dataclass
class Event:
    id: str            # unique ID (e.g., "day01-event03"), used for cross-references
    type: str          # landmark, restaurant, hotel, activity, transit, unknown
    name: str
    time_range: tuple[datetime, datetime]
    location: Location
    photos: list[Photo]
    description: str
    notes: str         # user-added
    sources: list[str] # what confirmed this: "exif", "itinerary", "credit_card", "google_maps", "apple_health", "dayone"

@dataclass
class Photo:
    path: Path
    timestamp: datetime
    gps: tuple[float, float] | None
    is_highlight: bool
    ai_description: str | None

@dataclass
class Location:
    lat: float
    lon: float
    name: str          # "Eiffel Tower", "Hotel Le Marais"
    address: str | None
    city: str
    country: str

@dataclass
class Transit:
    mode: str          # flight, car_rental, train, ferry, bus, taxi, walking
    departure: TransitPoint
    arrival: TransitPoint
    details: dict      # flexible: flight_number, rental_company, train_line, etc.
    sources: list[str]

@dataclass
class TransitPoint:
    location: Location
    time: datetime
    name: str          # "CDG Terminal 2", "Avis Nice Airport", "Gare de Lyon"

@dataclass
class Accommodation:
    name: str
    location: Location
    check_in: date
    check_out: date
    sources: list[str]

@dataclass
class Expense:
    date: date
    amount: float
    currency: str
    merchant: str
    category: str | None  # dining, transport, activity, shopping, etc.
    event_id: str | None  # ID of linked event if cross-referenced (serialization-friendly)
    source: str           # "spreadsheet" or "credit_card"
```

Expenses are ingested from the Excel workbook's expenses tab and optionally from the credit card CSV. They are stored on the `Trip` model (`expenses: list[Expense]`) and cross-referenced with events by date/time/location when possible. In the detailed record output, expenses appear as a summary section and are also noted on individual events where matched.

## V1 Outputs

### Detailed Personal Record (HTML)

A self-contained HTML file with embedded CSS and referenced images. Comprehensive and information-focused.

**Structure:**
- Trip header: destination, dates, travelers
- Day-by-day timeline with morning/afternoon/evening sections
- Each event: time range, location (with map link), AI-generated description, highlight photos, user notes
- Transit between stops
- Accommodations summary with addresses and dates
- Expense summary (pulled from spreadsheet, formatted as part of the document)
- Searchable via browser ctrl+F

Photos are referenced (not embedded) to keep file size manageable. The HTML file and a companion `photos/` folder with resized highlights are placed in the output directory.

### Shareable Summary (PDF + optional Blog HTML)

A curated 3-5 page highlight document for friends and family.

**Structure:**
- Cover: trip title, dates, hero photo
- Route overview: a static map image showing major stops, generated using a free tile-based map renderer (e.g., `staticmap` library with OpenStreetMap tiles) — no paid API needed
- 5-10 key highlights: photo, location, brief paragraph each
- "By the numbers": fun stats (countries, cities, distance walked, etc.)

Generated as PDF via WeasyPrint (free). Same content optionally output as blog-ready HTML.

## CLI Interface

### Commands

```
post-trip-summary new "<trip name>"       # Create a new session
post-trip-summary resume "<trip name>"    # Resume where you left off
post-trip-summary add-input "<trip name>" --photos <path>
                                          --excel <path>
                                          --credit-card <path>
                                          --google-maps <path>
                                          --apple-health <path>
                                          --dayone <path>
post-trip-summary preview "<trip name>"   # Open browser preview
post-trip-summary generate "<trip name>"  # Produce final outputs
post-trip-summary list                    # List all sessions
post-trip-summary delete "<trip name>"    # Delete a session (with confirmation)
```

### Session Persistence

```
~/.post-trip-summary/sessions/<trip-slug>/
├── config.json              # Input paths, settings, current stage
├── trip_data.json           # Stage 1: raw extracted data
├── trip_skeleton.json       # Stage 2: auto-generated timeline
├── trip_skeleton_reviewed.json  # Stage 3: user-reviewed timeline
├── trip_enriched.json       # Stage 4: AI-enriched data
├── trip_final.json          # Stage 5: fully reviewed
└── output/                  # Stage 6: generated files
    ├── detailed-record.html
    ├── photos/              # Resized highlight photos
    ├── shareable-summary.pdf
    └── blog-post.html       # Optional
```

## Technical Stack

| Component | Library | Cost |
|-----------|---------|------|
| CLI framework | click | Free |
| EXIF extraction | PyExifTool (bundled exiftool) | Free |
| Image handling | Pillow + pillow-heif | Free |
| Perceptual hashing | imagehash | Free |
| Reverse geocoding | reverse_geocoder | Free |
| Distance calculation | geopy | Free |
| Excel parsing | openpyxl | Free |
| AI vision | anthropic (Claude API) | Pay per use |
| Static maps | staticmap (OpenStreetMap tiles) | Free |
| PDF generation | WeasyPrint | Free |
| HTML templating | Jinja2 | Free |
| Preview server | FastAPI + uvicorn | Free |
| Data models | Python dataclasses | Free |

## Project Structure

```
PostTripSummary/
├── src/
│   └── post_trip_summary/
│       ├── __init__.py
│       ├── cli.py                  # CLI entry point (click)
│       ├── config.py               # Session config, paths, settings
│       ├── models.py               # Data models (Trip, Event, Photo, etc.)
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── ingest/
│       │   │   ├── __init__.py
│       │   │   ├── photos.py       # EXIF extraction, photo scanning
│       │   │   ├── excel.py        # Itinerary workbook parsing
│       │   │   ├── credit_card.py  # Transaction CSV parsing
│       │   │   ├── google_maps.py  # Google Takeout timeline parsing
│       │   │   ├── apple_health.py # Workout/route export parsing
│       │   │   └── dayone.py       # Day One journal export parsing
│       │   ├── skeleton.py         # Clustering, timeline building, cross-referencing
│       │   ├── enrich.py           # Vision API calls, landmark ID, photo selection
│       │   ├── review_skeleton.py  # Stage 3: interactive skeleton review
│       │   └── review_details.py   # Stage 5: interactive enrichment review
│       ├── output/
│       │   ├── __init__.py
│       │   ├── detailed_record.py  # HTML detailed record generator
│       │   ├── shareable_pdf.py    # PDF summary generator
│       │   └── blog_post.py        # Blog-formatted HTML generator
│       ├── vision/
│       │   ├── __init__.py
│       │   ├── client.py           # AI API abstraction layer
│       │   ├── triage.py           # Photo selection, dedup, cost estimation
│       │   └── prompts.py          # Prompt templates for vision tasks
│       ├── geo/
│       │   ├── __init__.py
│       │   ├── clustering.py       # Time/GPS photo clustering
│       │   └── reverse_geocode.py  # Offline reverse geocoding
│       ├── templates/              # Jinja2 templates (shared by output generators and preview)
│       │   ├── detailed_record.html
│       │   ├── shareable_summary.html
│       │   ├── blog_post.html
│       │   └── base.html           # Shared layout
│       └── preview/
│           ├── __init__.py
│           └── server.py           # Local FastAPI preview server (serves templates with live data)
├── exiftool_files/                 # Bundled exiftool for Windows
├── pyproject.toml
├── requirements.txt
└── README.md
```

## V2 Features (Future)

- **Interactive map/timeline**: HTML page with route visualization and clickable stops
- **Photo book layout**: Suggest organization and photo placement for print services (Shutterfly)
- **Video generation**: Slideshow with transitions, captions, background music for YouTube
- **WordPress integration**: Direct publishing via WordPress API
- **Local model fallback**: Run vision analysis locally when API is unavailable or for cost savings
- **Insta360/video input**: Incorporate 360 video and action camera footage
