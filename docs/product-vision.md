# Product Vision & UX Review

*Reviewed: 2026-03-22*

## What We've Built

A working pipeline that solves a real problem: turning a pile of vacation photos and scattered travel data into organized, shareable trip summaries. The engineering is solid — resumable stages, cost-gated AI calls, pluggable vision providers, browser-based review UIs. But it's currently an **engineering prototype**, not a product.

## The Core Insight Worth Protecting

The most valuable thing here isn't any single feature — it's the **pipeline philosophy**: photos are the primary data source, everything else enriches. Most travel apps start from itineraries or journals and treat photos as decoration. This project inverts that. A user's photos are the most honest record of what they actually did on a trip, not what they planned to do. That's a genuinely differentiated insight.

---

## Where the Current UX Falls Apart

### 1. The "assembly required" problem

Today's flow requires the user to:
- Install Python, ExifTool, WeasyPrint system libraries
- Configure API keys in a TOML file via `$EDITOR`
- Know which CLI commands to run in which order
- Understand what "stages" are and why they exist
- Manually provide paths to photos, Excel files, CSVs

A commercial user doesn't care about stages. They care about: "Here are my photos. Make something beautiful."

### 2. The input collection problem

Six data sources are supported (photos, Excel itinerary, credit card CSV, Google Maps timeline, Apple Health, Day One). But each requires the user to know:
- Where to export it from
- What format it should be in
- What the CLI flag is called

In practice, most users will have photos and *maybe* one other source. The Excel itinerary format is custom (requires specific sheet names). Credit card CSVs vary wildly by bank. Google Maps timeline export format changes. This is a lot of friction for incremental value.

### 3. The review UX is functional but disjointed

Three separate browser-based review UIs (skeleton review, photo cull, highlight picker) plus a CLI-based detail review. Each launches a local server, opens a browser tab, and waits. The user bounces between terminal and browser with no unified experience. The dark-themed skeleton review UI is actually quite nice, but it feels like a developer tool, not a consumer product.

### 4. The output identity crisis

Four outputs are generated: detailed record HTML, shareable PDF, blog post HTML, and organized photos. But who is the audience for each? The detailed record is a personal archive. The PDF is for sharing. The blog post is for publishing. The photo prep is for... what exactly? These serve different personas and use cases, but they're all generated together with no guidance on which to use when.

---

## Three Possible End States

### Option A: "The Personal Travel Archive" (Desktop App) — RECOMMENDED

**Target user:** Someone who takes lots of photos on trips, wants an organized record without spending hours in Lightroom or writing a blog post manually.

**What it looks like:**
- Native desktop app (Electron/Tauri) or high-quality web app running locally
- Drag-and-drop: user drops a folder of photos, app does the rest
- Single unified UI with a timeline view that builds in real-time as ingestion runs
- Sidebar for optional data sources: "Connect Google Maps," "Import itinerary," "Add expenses"
- The skeleton review becomes an inline editing experience — click an event name to rename it, drag events to merge them, right-click to change type
- Photo cull and highlight picking happen in the same view, not separate steps
- AI enrichment runs automatically in the background (with a settings toggle for "always approve" vs "ask first")
- Output is a beautiful, self-contained HTML file (like a Notion export) that the user can share, print, or keep

**The pipeline stages become invisible.** Instead of "ingest → skeleton → review → enrich → generate," the user sees:
1. **Import** (drop photos, optionally connect other sources)
2. **Review** (one screen: timeline with events, photos, and descriptions — all editable)
3. **Share** (export as PDF, HTML, or blog post)

**What changes architecturally:**
- The CLI becomes a build/debug tool, not the product
- The FastAPI server becomes the primary interface
- Review UIs merge into one SPA (React/Vue/Svelte)
- Pipeline runs asynchronously with progress indicators
- Settings live in the UI, not a TOML file

**Monetization:** One-time purchase ($20-30) or open source with optional cloud sync.

---

### Option B: "The Trip Storyteller" (Web SaaS)

**Target user:** Travelers who want to share trip stories with friends and family without the effort of writing a blog post or making a photo album.

**What it looks like:**
- Web app with auth and cloud storage
- Upload flow: drag photos → processing happens server-side → user gets a draft story in 2-3 minutes
- The output is a beautiful, interactive web page (think: a personal Airbnb Experience page for your trip)
- Social features: share via link, embed on social media, collaborative editing (travel companions add their photos)
- AI writes the narrative, user just edits and approves
- Templates/themes for different trip types (road trip, beach vacation, city exploration, hiking adventure)

**What the user does vs. what happens automatically:**

| Step | User Action | System Action |
|------|------------|---------------|
| Upload | Drops photo folder | Extracts EXIF, scores quality, culls duplicates |
| Connect (optional) | Links Google account | Pulls Maps timeline, auto-correlates with photos |
| Wait | Sees progress bar | Clusters, geocodes, enriches with AI |
| Review | Sees draft story, makes edits | Presents timeline with suggested names, AI descriptions |
| Customize | Picks theme, reorders sections | Renders in chosen template |
| Share | Clicks "Share" | Generates link, creates PDF backup |

**What changes architecturally:**
- Everything moves server-side (no local installs)
- Photo storage becomes a real concern (S3/R2)
- Reverse geocoding can use Google Maps API (better data, costs money)
- AI enrichment is a product cost, not a user cost
- Need user accounts, billing, and storage management

**Monetization:** Freemium — 1 free trip, then $5/trip or $30/year unlimited.

---

### Option C: "The Trip Processing Engine" (Developer Tool / API)

**Target user:** Other developers building travel apps, photo organizers, or journaling tools.

**What it looks like:**
- Published Python package on PyPI
- Clean API: `engine = TripEngine(); trip = engine.process(photos_dir="/path", options={...})`
- Webhook/callback system for review steps (or skip them for full auto)
- Pluggable output renderers
- Docker image for easy deployment

This is closest to what exists now, but with the CLI stripped away and a proper programmatic API exposed. The value proposition is: "Don't build photo clustering, reverse geocoding, and AI enrichment yourself. Use our engine."

**Monetization:** Open source core + paid hosted API, or consulting/integration fees.

---

## Why Option A Is the Recommended Direction

- The hard parts are already built (pipeline, clustering, geocoding, AI enrichment)
- The browser-based review UIs prove visual interaction thinking is already present
- A desktop/local-first app preserves the "no cloud, no subscription" ethos
- The jump from "FastAPI server + HTML templates" to "single-page app with embedded server" is incremental, not a rewrite
- Full control of the user's data (no cloud storage concerns)

---

## Highest-Impact Changes

1. **Unify the review experience into a single timeline view.** The user should never leave one screen. Event editing, photo culling, and highlight picking should all happen on the same page. Think of it like a vertical timeline — each event is a card with its photos, and you can expand, edit, merge, delete, and annotate inline.

2. **Make the pipeline invisible.** Run ingest + skeleton + auto-enrich as one async operation. Show a progress indicator. The user's first interaction should be the review screen, not a terminal.

3. **Reduce input friction to drag-and-drop.** Photos are the only required input. Everything else should be "Connect" buttons in a settings panel (Google Maps, Apple Health) or file drop zones (itinerary, expenses). Don't ask for formats — detect them.

4. **Pick one primary output and make it exceptional.** The shareable summary PDF is the hero output. Make it gorgeous. The detailed record and blog post are secondary exports. Don't split focus across four mediocre outputs.

5. **Make AI enrichment the default, not a gate.** If the user has configured an API key (or you bundle Gemini Flash free tier), just run it. Show a small "AI credits used" indicator. The cost approval flow breaks the magic of "drop photos, get story."

---

## What Users Expect to Be Automatic vs. Manual

### Should be fully automatic (user never sees it)
- EXIF extraction and GPS parsing
- Photo quality scoring and duplicate removal
- Clustering photos into events
- Reverse geocoding event locations
- Cross-referencing with connected data sources
- AI photo descriptions (if API key configured)
- Selecting representative/highlight photos (initial suggestion)
- Generating the output documents

### Should be automatic with easy override (user sees result, can change it)
- Event names (auto-generated, editable inline)
- Event types (auto-classified, changeable via dropdown)
- Which photos are kept vs. culled (auto-culled, but user can restore)
- Which photos are highlights (auto-selected, user can toggle)
- Event grouping/merging (auto-clustered, user can split or merge)

### Should require explicit user input
- Choosing which photos/folder to process (the starting action)
- Trip name and date range (though date range should be auto-detected from photos)
- Final "looks good, generate" confirmation
- Sharing/exporting (user chooses format and destination)

### Should never require user input in a commercial product
- API key configuration (bundle it or use OAuth)
- Installing system dependencies
- Understanding pipeline stages
- Knowing CLI commands
- File format requirements for supplementary data

---

## The Bottom Line

The pipeline design, the photos-first philosophy, and the cost-conscious AI integration are all smart choices. What's missing is the **product wrapper** — the thing that turns "a pipeline you run from the terminal" into "an experience where you drop your photos and get a beautiful trip story." The bones are good. Now it needs skin.
