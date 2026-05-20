# Trip Story Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `trip-story.html` as the new primary, polished, shareable HTML output while leaving the existing detailed record, PDF, blog post, and photo prep outputs intact.

**Architecture:** Add a focused `post_trip_summary.output.trip_story` renderer that prepares a small presentation context from existing `Trip`, `Day`, `Event`, and `Photo` dataclasses, then renders a new Jinja template. Wire the renderer into CLI generation, the browser Generate page, and a new `/story` preview endpoint without changing the pipeline or data model.

**Tech Stack:** Python 3.10+, dataclasses, Jinja2 templates, Click CLI, FastAPI server, pytest.

---

## File Structure

- `src/post_trip_summary/output/trip_story.py`
  - New focused output module.
  - Owns Trip Story presentation helpers and `generate_trip_story()`.
  - Does not mutate the `Trip`.

- `src/post_trip_summary/templates/trip_story.html`
  - New self-contained editorial HTML template.
  - Uses existing `/photos/{filename}` serving behavior in preview and copied `photos/<stem>.jpg` paths in generated output.

- `src/post_trip_summary/server/app.py`
  - Add Trip Story generation support in `POST /api/generate`.
  - Add `GET /story` preview endpoint.

- `src/post_trip_summary/templates/generate.html`
  - Add Trip Story as the first, checked output option.

- `src/post_trip_summary/cli.py`
  - Generate `trip-story.html` during CLI `post-trip-summary generate`.

- `tests/test_trip_story_output.py`
  - New unit tests for Trip Story helpers and rendered output.

- `tests/test_server_app.py`
  - Add server generate and preview coverage for Trip Story.

- `tests/test_cli_pipeline.py`
  - Add CLI generation coverage for Trip Story wiring.

- `README.md`
  - Update output documentation so Trip Story is described as the primary output.

---

### Task 1: Add Trip Story Presentation Helpers

**Files:**
- Create: `src/post_trip_summary/output/trip_story.py`
- Create: `tests/test_trip_story_output.py`

- [ ] **Step 1: Write failing tests for cover selection, stats, location summary, and highlights**

Create `tests/test_trip_story_output.py`:

```python
from datetime import date, datetime
from pathlib import Path

from post_trip_summary.models import Day, Event, Location, Photo, Trip


def _photo(
    name: str,
    *,
    day: int = 5,
    hour: int = 10,
    is_highlight: bool = False,
    is_kept: bool = True,
    quality_score: float | None = None,
) -> Photo:
    return Photo(
        path=Path(f"/photos/{name}.jpg"),
        timestamp=datetime(2026, 3, day, hour, 0),
        gps=(48.858, 2.294),
        is_highlight=is_highlight,
        is_kept=is_kept,
        quality_score=quality_score,
        ai_description=f"{name} description",
    )


def _event(
    event_id: str,
    name: str,
    city: str,
    country: str,
    photos: list[Photo],
    *,
    description: str = "A memorable stop.",
) -> Event:
    loc = Location(
        lat=48.858,
        lon=2.294,
        name=name,
        address=None,
        city=city,
        country=country,
    )
    return Event(
        id=event_id,
        type="landmark",
        name=name,
        time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 11, 0)),
        location=loc,
        photos=photos,
        description=description,
        notes="",
        sources=["exif"],
    )


def _trip() -> Trip:
    day1 = Day(
        date=date(2026, 3, 5),
        events=[
            _event(
                "day01-event01",
                "Eiffel Tower",
                "Paris",
                "France",
                [
                    _photo("low-highlight", is_highlight=True, quality_score=40),
                    _photo("best-highlight", is_highlight=True, quality_score=95),
                    _photo("removed-highlight", is_highlight=True, is_kept=False, quality_score=100),
                ],
            )
        ],
    )
    day2 = Day(
        date=date(2026, 3, 6),
        events=[
            _event(
                "day02-event01",
                "Louvre",
                "Paris",
                "France",
                [_photo("louvre", day=6, is_highlight=False, quality_score=80)],
            )
        ],
    )
    return Trip(
        name="Paris 2026",
        date_range=(date(2026, 3, 5), date(2026, 3, 6)),
        days=[day1, day2],
    )


def test_select_cover_photo_prefers_highest_quality_kept_highlight():
    from post_trip_summary.output.trip_story import select_cover_photo

    cover = select_cover_photo(_trip())

    assert cover is not None
    assert cover.path.name == "best-highlight.jpg"


def test_select_cover_photo_falls_back_to_first_kept_photo_when_no_highlights():
    from post_trip_summary.output.trip_story import select_cover_photo

    trip = Trip(
        name="Fallback",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[
            Day(
                date=date(2026, 3, 5),
                events=[
                    _event(
                        "day01-event01",
                        "Walk",
                        "Paris",
                        "France",
                        [_photo("first-kept", is_highlight=False)],
                    )
                ],
            )
        ],
    )

    cover = select_cover_photo(trip)

    assert cover is not None
    assert cover.path.name == "first-kept.jpg"


def test_compute_story_stats_counts_kept_photos_and_locations():
    from post_trip_summary.output.trip_story import compute_story_stats

    stats = compute_story_stats(_trip())

    assert stats == {
        "days": 2,
        "stops": 2,
        "photos": 3,
        "highlights": 2,
        "cities": 1,
        "countries": 1,
    }


def test_location_summary_uses_ordered_unique_locations():
    from post_trip_summary.output.trip_story import build_location_summary

    assert build_location_summary(_trip()) == "Paris, France"


def test_select_highlight_photos_returns_kept_highlights_only():
    from post_trip_summary.output.trip_story import select_highlight_photos

    photos = select_highlight_photos(_trip())

    assert [p.path.name for p in photos] == ["low-highlight.jpg", "best-highlight.jpg"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trip_story_output.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'post_trip_summary.output.trip_story'`.

- [ ] **Step 3: Implement the helper module**

Create `src/post_trip_summary/output/trip_story.py`:

```python
"""Generate the polished Trip Story HTML output."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Day, Event, Photo, Trip


def _all_events(trip: Trip) -> list[Event]:
    return [event for day in trip.days for event in day.events]


def _kept_photos(event: Event) -> list[Photo]:
    return [photo for photo in event.photos if photo.is_kept]


def _ordered_unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        clean = value.strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def select_highlight_photos(trip: Trip, max_count: int = 12) -> list[Photo]:
    """Return kept highlight photos in trip order."""
    photos = [
        photo
        for event in _all_events(trip)
        for photo in event.photos
        if photo.is_kept and photo.is_highlight
    ]
    return photos[:max_count]


def select_cover_photo(trip: Trip) -> Photo | None:
    """Choose the best cover photo using Phase 1 defaults."""
    kept_highlights = [
        photo
        for event in _all_events(trip)
        for photo in event.photos
        if photo.is_kept and photo.is_highlight
    ]
    if kept_highlights:
        return max(
            kept_highlights,
            key=lambda photo: photo.quality_score if photo.quality_score is not None else -1,
        )

    for event in _all_events(trip):
        kept = _kept_photos(event)
        if kept:
            return kept[0]
    return None


def compute_story_stats(trip: Trip) -> dict[str, int]:
    """Compute story-facing stats from kept photos and all timeline events."""
    events = _all_events(trip)
    kept_photos = [photo for event in events for photo in event.photos if photo.is_kept]
    highlights = [photo for photo in kept_photos if photo.is_highlight]
    cities = {event.location.city for event in events if event.location.city}
    countries = {event.location.country for event in events if event.location.country}
    return {
        "days": (trip.date_range[1] - trip.date_range[0]).days + 1,
        "stops": len(events),
        "photos": len(kept_photos),
        "highlights": len(highlights),
        "cities": len(cities),
        "countries": len(countries),
    }


def build_location_summary(trip: Trip) -> str:
    """Build a compact location summary for the story cover."""
    events = _all_events(trip)
    countries = _ordered_unique([event.location.country for event in events if event.location.country])
    cities = _ordered_unique([event.location.city for event in events if event.location.city])

    if len(countries) == 1 and len(cities) == 1:
        return f"{cities[0]}, {countries[0]}"
    if len(countries) == 1 and cities:
        if len(cities) <= 3:
            return f"{', '.join(cities)}, {countries[0]}"
        return f"{len(cities)} cities in {countries[0]}"
    if countries:
        return ", ".join(countries[:3]) if len(countries) <= 3 else f"{len(countries)} countries"
    if cities:
        return ", ".join(cities[:3])
    return ""


def _event_has_story_content(event: Event) -> bool:
    return bool(event.description or event.notes or _kept_photos(event))


def days_with_story_content(trip: Trip) -> list[Day]:
    """Return days that have at least one event worth showing in the story."""
    return [
        day
        for day in trip.days
        if any(_event_has_story_content(event) for event in day.events)
    ]


def build_story_context(trip: Trip, map_image: str | None = None) -> dict:
    """Build the template context for Trip Story rendering."""
    return {
        "trip": trip,
        "cover_photo": select_cover_photo(trip),
        "location_summary": build_location_summary(trip),
        "stats": compute_story_stats(trip),
        "highlight_photos": select_highlight_photos(trip),
        "story_days": days_with_story_content(trip),
        "map_image": map_image,
    }


def generate_trip_story(trip: Trip, output_path: Path, map_image: str | None = None) -> None:
    """Render the Trip Story HTML output."""
    from post_trip_summary.output.detailed_record import _format_time_filter, _photo_url_filter

    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    env.filters["ftime"] = _format_time_filter
    env.filters["photo_url"] = _photo_url_filter
    template = env.get_template("trip_story.html")
    html = template.render(**build_story_context(trip, map_image=map_image))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trip_story_output.py -v
```

Expected: PASS for the five helper tests.

- [ ] **Step 5: Commit**

```powershell
git add src/post_trip_summary/output/trip_story.py tests/test_trip_story_output.py
git commit -m "Add Trip Story output helpers"
```

---

### Task 2: Add the Trip Story HTML Template and Renderer Test

**Files:**
- Create: `src/post_trip_summary/templates/trip_story.html`
- Modify: `tests/test_trip_story_output.py`

- [ ] **Step 1: Add a failing render test**

Append to `tests/test_trip_story_output.py`:

```python
def test_generate_trip_story_writes_editorial_html(tmp_path):
    from post_trip_summary.output.trip_story import generate_trip_story

    output_path = tmp_path / "trip-story.html"
    generate_trip_story(_trip(), output_path, map_image="route-map.png")

    html = output_path.read_text(encoding="utf-8")
    assert output_path.exists()
    assert "Paris 2026" in html
    assert "Paris, France" in html
    assert "route-map.png" in html
    assert "Eiffel Tower" in html
    assert "By the Numbers" in html
    assert "best-highlight.jpg" in html
    assert "Trip Story" in html
```

- [ ] **Step 2: Run the render test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trip_story_output.py::test_generate_trip_story_writes_editorial_html -v
```

Expected: FAIL with `jinja2.exceptions.TemplateNotFound: trip_story.html`.

- [ ] **Step 3: Create the Trip Story template**

Create `src/post_trip_summary/templates/trip_story.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ trip.name }} - Trip Story</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Georgia, "Times New Roman", serif;
            color: #27231f;
            background: #f7f1e8;
            line-height: 1.65;
        }
        img { max-width: 100%; display: block; }
        .story-hero {
            min-height: 72vh;
            display: flex;
            align-items: flex-end;
            position: relative;
            color: #fff;
            background: #2c3531;
        }
        .story-hero.has-cover {
            background-size: cover;
            background-position: center;
        }
        .story-hero::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, rgba(0,0,0,0.16), rgba(0,0,0,0.68));
        }
        .hero-inner {
            position: relative;
            width: min(1100px, 100%);
            margin: 0 auto;
            padding: 4rem 2rem;
        }
        .kicker {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.75rem;
            font-weight: 700;
            color: #f4d7a1;
        }
        h1 {
            margin: 0.2rem 0 0.5rem;
            font-size: clamp(2.6rem, 8vw, 6.5rem);
            line-height: 0.95;
            letter-spacing: 0;
        }
        .subtitle {
            max-width: 720px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: clamp(1rem, 2.5vw, 1.35rem);
            color: rgba(255,255,255,0.9);
        }
        .story-shell {
            width: min(1040px, 100%);
            margin: 0 auto;
            padding: 3rem 1.25rem 4rem;
        }
        .intro-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.4fr) minmax(220px, 0.6fr);
            gap: 2rem;
            align-items: start;
            margin-bottom: 3rem;
        }
        .intro-card, .stats-card {
            border-top: 1px solid #d8c5a7;
            padding-top: 1.25rem;
        }
        .lede {
            font-size: clamp(1.3rem, 3vw, 2rem);
            line-height: 1.35;
            margin: 0;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }
        .stat-number {
            display: block;
            font-size: 1.7rem;
            font-weight: 750;
            color: #31584c;
        }
        .stat-label {
            display: block;
            color: #6f665c;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .route-map {
            margin: 0 0 3rem;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #ddcfb8;
        }
        .highlight-reel {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.5rem;
            margin: 2rem 0 4rem;
        }
        .highlight-reel img {
            width: 100%;
            aspect-ratio: 1;
            object-fit: cover;
            border-radius: 6px;
        }
        .day-section {
            margin: 0 0 4rem;
        }
        .day-header {
            margin-bottom: 1.5rem;
            border-bottom: 1px solid #d8c5a7;
            padding-bottom: 0.75rem;
        }
        .day-header h2 {
            margin: 0;
            font-size: clamp(1.8rem, 4vw, 3rem);
            line-height: 1.05;
        }
        .day-date {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #756b5f;
            font-size: 0.95rem;
        }
        .event-block {
            margin: 0 0 2.5rem;
        }
        .event-meta {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #756b5f;
            font-size: 0.9rem;
            margin-bottom: 0.35rem;
        }
        .event-block h3 {
            margin: 0 0 0.55rem;
            font-size: clamp(1.35rem, 3vw, 2rem);
            line-height: 1.1;
        }
        .event-description {
            max-width: 760px;
            margin: 0 0 1rem;
            font-size: 1.05rem;
        }
        .event-notes {
            max-width: 720px;
            margin: 1rem 0;
            padding-left: 1rem;
            border-left: 3px solid #c98255;
            color: #5f554b;
            font-style: italic;
        }
        .photo-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.65rem;
            margin-top: 1rem;
        }
        .photo-grid img {
            width: 100%;
            aspect-ratio: 4 / 3;
            object-fit: cover;
            border-radius: 6px;
        }
        .story-footer {
            border-top: 1px solid #d8c5a7;
            padding-top: 2rem;
            color: #756b5f;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 0.9rem;
        }
        @media (max-width: 760px) {
            .intro-grid { grid-template-columns: 1fr; }
            .highlight-reel { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .photo-grid { grid-template-columns: 1fr; }
            .hero-inner { padding: 3rem 1.25rem; }
        }
    </style>
</head>
<body>
    <header class="story-hero {% if cover_photo %}has-cover{% endif %}"
            {% if cover_photo %}style="background-image: url('{{ cover_photo.path | photo_url }}');"{% endif %}>
        <div class="hero-inner">
            <div class="kicker">Trip Story</div>
            <h1>{{ trip.name }}</h1>
            <div class="subtitle">
                {{ trip.date_range[0].strftime('%B %d') }} - {{ trip.date_range[1].strftime('%B %d, %Y') }}
                {% if location_summary %}<br>{{ location_summary }}{% endif %}
            </div>
        </div>
    </header>

    <main class="story-shell">
        <section class="intro-grid" aria-label="Trip overview">
            <div class="intro-card">
                <p class="lede">
                    A photo-led record of {{ trip.name }}{% if location_summary %}, following the route through {{ location_summary }}{% endif %}.
                </p>
            </div>
            <aside class="stats-card" aria-label="By the Numbers">
                <div class="kicker">By the Numbers</div>
                <div class="stats-grid">
                    <div><span class="stat-number">{{ stats.days }}</span><span class="stat-label">Days</span></div>
                    <div><span class="stat-number">{{ stats.stops }}</span><span class="stat-label">Stops</span></div>
                    <div><span class="stat-number">{{ stats.photos }}</span><span class="stat-label">Photos</span></div>
                    <div><span class="stat-number">{{ stats.highlights }}</span><span class="stat-label">Highlights</span></div>
                </div>
            </aside>
        </section>

        {% if map_image %}
        <section class="route-map" aria-label="Trip route">
            <img src="{{ map_image }}" alt="Trip route map">
        </section>
        {% endif %}

        {% if highlight_photos %}
        <section aria-label="Highlight photos">
            <div class="kicker">Highlights</div>
            <div class="highlight-reel">
                {% for photo in highlight_photos %}
                <img src="{{ photo.path | photo_url }}" alt="{{ photo.ai_description or trip.name }}">
                {% endfor %}
            </div>
        </section>
        {% endif %}

        {% for day in story_days %}
        <section class="day-section">
            <header class="day-header">
                <div class="day-date">{{ day.date.strftime('%A, %B %d') }}</div>
                <h2>Day {{ loop.index }}</h2>
            </header>

            {% for event in day.events %}
            {% set kept_photos = event.photos | selectattr('is_kept') | list %}
            {% set event_highlights = kept_photos | selectattr('is_highlight') | list %}
            {% if event.description or event.notes or kept_photos %}
            <article class="event-block">
                <div class="event-meta">
                    {{ event.time_range[0] | ftime }}
                    {% if event.location.name %} · {{ event.location.name }}{% endif %}
                    {% if event.location.city %} · {{ event.location.city }}{% endif %}
                </div>
                <h3>{{ event.name }}</h3>
                {% if event.description %}
                <p class="event-description">{{ event.description }}</p>
                {% endif %}
                {% if event.notes %}
                <blockquote class="event-notes">{{ event.notes }}</blockquote>
                {% endif %}
                {% if event_highlights %}
                <div class="photo-grid">
                    {% for photo in event_highlights[:6] %}
                    <img src="{{ photo.path | photo_url }}" alt="{{ photo.ai_description or event.name }}">
                    {% endfor %}
                </div>
                {% elif kept_photos %}
                <div class="photo-grid">
                    {% for photo in kept_photos[:3] %}
                    <img src="{{ photo.path | photo_url }}" alt="{{ photo.ai_description or event.name }}">
                    {% endfor %}
                </div>
                {% endif %}
            </article>
            {% endif %}
            {% endfor %}
        </section>
        {% endfor %}

        <footer class="story-footer">
            Generated locally with Post-Trip Summary.
        </footer>
    </main>
</body>
</html>
```

- [ ] **Step 4: Run the render test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trip_story_output.py -v
```

Expected: PASS for all Trip Story output tests.

- [ ] **Step 5: Commit**

```powershell
git add src/post_trip_summary/templates/trip_story.html tests/test_trip_story_output.py
git commit -m "Add Trip Story HTML template"
```

---

### Task 3: Wire Trip Story Into Browser Generate and Preview

**Files:**
- Modify: `src/post_trip_summary/server/app.py`
- Modify: `src/post_trip_summary/templates/generate.html`
- Modify: `tests/test_server_app.py`

- [ ] **Step 1: Add failing server tests**

Append to `tests/test_server_app.py`:

```python
def test_generate_api_trip_story(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app, _build_event_index

    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)

    response = client.post("/api/generate", json={
        "trip_story": True,
        "detailed_record": False,
        "shareable_pdf": False,
        "blog_post": False,
        "photo_prep": False,
    })

    assert response.status_code == 200
    data = response.json()
    assert any(f["type"] == "trip_story" for f in data["files"])
    assert (session.output_dir / "trip-story.html").exists()


def test_preview_story_endpoint(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app, _build_event_index

    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)

    response = client.get("/story")

    assert response.status_code == 200
    assert "Trip Story" in response.text
    assert "Test" in response.text
```

- [ ] **Step 2: Run server tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_server_app.py -v -k "trip_story or preview_story"
```

Expected: FAIL because `trip_story` is not generated and `/story` does not exist.

- [ ] **Step 3: Update the Generate template option list**

In `src/post_trip_summary/templates/generate.html`, add Trip Story as the first checkbox inside `<div class="option-group">`:

```html
        <label class="option-label">
            <input type="checkbox" id="opt-story" checked>
            <span class="option-info">
                <strong>Trip Story</strong>
                <span class="option-desc">Polished, photo-forward HTML story for sharing or keeping</span>
            </span>
        </label>
```

In the `<script>` block, update `TYPE_LABELS`:

```javascript
const TYPE_LABELS = {
    trip_story: "Trip Story",
    detailed_record: "Detailed Record",
    shareable_pdf: "Shareable Summary",
    blog_post: "Blog Post",
    photo_prep: "Photo Prep",
};
```

In `generateOutputs()`, add `trip_story` to the `outputs` object:

```javascript
    const outputs = {
        trip_story: document.getElementById('opt-story').checked,
        detailed_record: document.getElementById('opt-detailed').checked,
        shareable_pdf: document.getElementById('opt-pdf').checked,
        blog_post: document.getElementById('opt-blog').checked,
        photo_prep: document.getElementById('opt-photos').checked,
    };
```

- [ ] **Step 4: Update `POST /api/generate` and add `/story` preview**

In `src/post_trip_summary/server/app.py`, inside `api_generate()` after route map generation and before existing output generation blocks, add:

```python
        if body.get("trip_story"):
            from post_trip_summary.output.trip_story import generate_trip_story
            out = output_dir / "trip-story.html"
            generate_trip_story(trip, out, map_image=map_image)
            files.append({
                "type": "trip_story",
                "path": str(out),
                "preview_url": "/story",
            })
```

Move the existing route map generation line so it runs before the Trip Story and PDF blocks:

```python
        # Generate route map for story/PDF outputs
        map_image = _generate_static_map(trip, output_dir)
```

Add a preview endpoint near the other output preview endpoints:

```python
    @app.get("/story", response_class=HTMLResponse)
    def preview_story():
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        from post_trip_summary.output.trip_story import build_story_context
        template = env.get_template("trip_story.html")
        return HTMLResponse(template.render(**build_story_context(
            app.state.trip,
            map_image=None,
        )))
```

- [ ] **Step 5: Run server tests to verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_server_app.py -v -k "generate_api_trip_story or preview_story_endpoint or generate_page_renders"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/post_trip_summary/server/app.py src/post_trip_summary/templates/generate.html tests/test_server_app.py
git commit -m "Wire Trip Story into browser generation"
```

---

### Task 4: Wire Trip Story Into CLI Generation

**Files:**
- Modify: `src/post_trip_summary/cli.py`
- Modify: `tests/test_cli_pipeline.py`

- [ ] **Step 1: Add a failing CLI wiring test**

Append to `tests/test_cli_pipeline.py`:

```python
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from post_trip_summary.config import create_session
from post_trip_summary.models import Day, Event, Location, Photo, Trip
from post_trip_summary.serialization import save_trip


def _final_trip(tmp_path) -> Trip:
    photo_path = tmp_path / "photo.jpg"
    photo_path.write_bytes(b"not-used-by-patched-generators")
    photo = Photo(
        path=photo_path,
        timestamp=datetime(2026, 3, 5, 10, 0),
        gps=(48.858, 2.294),
        is_highlight=True,
        is_kept=True,
    )
    event = Event(
        id="day01-event01",
        type="landmark",
        name="Eiffel Tower",
        time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 11, 0)),
        location=Location(
            lat=48.858,
            lon=2.294,
            name="Eiffel Tower",
            address=None,
            city="Paris",
            country="France",
        ),
        photos=[photo],
        description="A visit to the Eiffel Tower.",
    )
    return Trip(
        name="Paris 2026",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )


def test_generate_command_creates_trip_story(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    save_trip(_final_trip(tmp_path), session.stage_file("final"))

    with patch("post_trip_summary.cli._generate_static_map", return_value=None), \
         patch("post_trip_summary.output.photo_prep.prepare_photos"), \
         patch("post_trip_summary.output.detailed_record.generate_detailed_record"), \
         patch("post_trip_summary.output.shareable_pdf.generate_shareable_pdf"), \
         patch("post_trip_summary.output.blog_post.generate_blog_post"), \
         patch("post_trip_summary.output.trip_story.generate_trip_story") as story:
        result = runner.invoke(cli, ["generate", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    story.assert_called_once()
    assert "Generating trip story" in result.output
```

- [ ] **Step 2: Run the CLI test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_pipeline.py::test_generate_command_creates_trip_story -v
```

Expected: FAIL because the CLI does not call `generate_trip_story()`.

- [ ] **Step 3: Update the CLI generate command**

In `src/post_trip_summary/cli.py`, inside `generate()`, add the import:

```python
    from post_trip_summary.output.trip_story import generate_trip_story
```

After route map generation and before detailed record generation, add:

```python
    click.echo("  Generating trip story...")
    generate_trip_story(trip, output_dir / "trip-story.html", map_image=map_path)
```

The relevant block should read:

```python
    click.echo("  Preparing photos...")
    prepare_photos(trip, output_dir)

    click.echo("  Generating route map...")
    map_path = _generate_static_map(trip, output_dir)

    click.echo("  Generating trip story...")
    generate_trip_story(trip, output_dir / "trip-story.html", map_image=map_path)

    click.echo("  Generating detailed record...")
    generate_detailed_record(trip, output_dir / "detailed-record.html")
```

- [ ] **Step 4: Run the CLI test to verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cli_pipeline.py::test_generate_command_creates_trip_story -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/post_trip_summary/cli.py tests/test_cli_pipeline.py
git commit -m "Add Trip Story to CLI generation"
```

---

### Task 5: Update README Output Positioning

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Outputs section**

In `README.md`, replace the current Outputs list:

```markdown
- **Detailed record** — Full HTML document with every event, photo, and note
- **Shareable PDF** — A summary with route map suitable for sharing
- **Blog post** — HTML formatted for publishing
- **Photo prep** — Organized and selected highlight photos
```

with:

```markdown
- **Trip Story** — Primary polished HTML story with cover photo, day-by-day narrative, highlights, route map, and trip stats
- **Detailed record** — Full archive HTML document with every event, photo, note, source, and supporting detail
- **Shareable PDF** — PDF summary with route map suitable for sharing
- **Blog post** — HTML formatted for publishing
- **Photo prep** — Organized and selected highlight photos
```

- [ ] **Step 2: Update the Generate stage description**

In the Pipeline stages table, replace:

```markdown
| **Generate** | Produces output files: detailed HTML record, shareable PDF, blog post, and a route map |
```

with:

```markdown
| **Generate** | Produces the primary Trip Story plus optional detailed record, shareable PDF, blog post, photo prep, and route map |
```

- [ ] **Step 3: Commit**

```powershell
git add README.md
git commit -m "Document Trip Story as primary output"
```

---

### Task 6: Final Verification

**Files:**
- No source edits.

- [ ] **Step 1: Run focused output tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_trip_story_output.py tests/test_output.py -v
```

Expected: PASS.

- [ ] **Step 2: Run focused server and CLI tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_server_app.py tests/test_cli_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass with the existing `pytest.mark.integration` warning still acceptable.

- [ ] **Step 4: Inspect final diff**

Run:

```powershell
git diff --stat HEAD
git status --short
```

Expected: only files from this plan are modified, and there are no unexpected unrelated changes staged or unstaged by the implementation.

---

## Manual Smoke Test

After Task 6 passes, test against an existing completed session if one is available:

```powershell
post-trip-summary generate <slug>
post-trip-summary start <slug>
```

Expected:

- CLI generation writes `trip-story.html` to the session output directory.
- Browser Generate page shows Trip Story as the first checked option.
- Browser Generate API creates `trip-story.html` when selected.
- `/story` preview renders the Trip Story HTML.
- Existing `/detailed`, `/summary`, and `/blog` previews still render.

