# Vacation Blend Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 2A metadata-only Vacation Blend Discovery with persisted theme results, a browser review page, and a CLI/debug command.

**Architecture:** Add a new `post_trip_summary.discovery` package for taxonomy, dataclasses, metadata scoring, persistence, and session service orchestration. Insert a `discovered` stage between `reviewed` and `enriched`, and add a simple browser page where users can accept or edit detected primary/secondary theme chips. Keep local AI, cloud synthesis, Trip Story curation, story density, and recommendation logic out of this phase.

**Tech Stack:** Python 3.10+, dataclasses, Click CLI, FastAPI, Jinja2, pytest.

---

## File Structure

- `src/post_trip_summary/discovery/__init__.py`
  - Package marker and public exports for discovery models/service helpers.

- `src/post_trip_summary/discovery/models.py`
  - Dataclasses: `ThemeDefinition`, `ThemeScore`, `VacationBlend`.
  - Confidence constants and small validation helpers.

- `src/post_trip_summary/discovery/taxonomy.py`
  - Central controlled theme taxonomy and theme-id validation.

- `src/post_trip_summary/discovery/serialization.py`
  - JSON encode/decode, save/load helpers for `<session_dir>/vacation_blend.json`.

- `src/post_trip_summary/discovery/metadata.py`
  - Deterministic metadata-only scoring algorithm.
  - Produces `VacationBlend` from an existing `Trip`.

- `src/post_trip_summary/discovery/service.py`
  - Session-level orchestration: load reviewed trip, run discovery, save artifact, optionally advance stage.

- `src/post_trip_summary/config.py`
  - Add `discovered` stage.
  - Add safe discovery defaults under `DEFAULT_SETTINGS`.

- `src/post_trip_summary/server/app.py`
  - Update wizard routing/stage maps.
  - Add `/wizard/discovery`.
  - Add `/api/discovery/update`.

- `src/post_trip_summary/templates/wizard.html`
  - Add Discovery to the wizard step indicator.

- `src/post_trip_summary/templates/review.html`
  - Change continue button copy from "Continue to Enrichment" to "Continue to Discovery".

- `src/post_trip_summary/templates/discovery.html`
  - New browser review page for Vacation Blend theme chips and diagnostics.

- `src/post_trip_summary/cli.py`
  - Add `post-trip-summary discover <slug>` command.

- `README.md`
  - Document the new `discover` command and Discovery stage.

- `tests/test_discovery_models.py`
  - Taxonomy, validation, and JSON round-trip tests.

- `tests/test_discovery_metadata.py`
  - Deterministic metadata scoring tests.

- `tests/test_discovery_service.py`
  - Session artifact and stage-advance tests.

- `tests/test_server_app.py`
  - Wizard Discovery page and update endpoint tests.

- `tests/test_cli_pipeline.py`
  - CLI `discover` command test.

---

### Task 1: Add Discovery Models, Taxonomy, and Serialization

**Files:**
- Create: `src/post_trip_summary/discovery/__init__.py`
- Create: `src/post_trip_summary/discovery/models.py`
- Create: `src/post_trip_summary/discovery/taxonomy.py`
- Create: `src/post_trip_summary/discovery/serialization.py`
- Create: `tests/test_discovery_models.py`

- [ ] **Step 1: Write failing model, taxonomy, and serialization tests**

Create `tests/test_discovery_models.py`:

```python
from pathlib import Path

import pytest

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.serialization import (
    decode_vacation_blend,
    encode_vacation_blend,
    load_vacation_blend,
    save_vacation_blend,
)
from post_trip_summary.discovery.taxonomy import THEME_BY_ID, validate_theme_ids


def test_taxonomy_has_expected_theme_ids():
    expected = {
        "road_trip",
        "adventure_outdoors",
        "nature_wildlife",
        "culture_sightseeing",
        "food_drink",
        "people_social",
        "nightlife_events",
        "beach_relaxation",
        "resort_luxury",
        "family_milestone",
    }

    assert set(THEME_BY_ID) == expected
    assert THEME_BY_ID["road_trip"].label == "Road Trip"
    assert THEME_BY_ID["beach_relaxation"].label == "Beach & Relaxation"


def test_validate_theme_ids_rejects_unknown():
    with pytest.raises(ValueError, match="unknown theme id"):
        validate_theme_ids(["road_trip", "made_up_theme"])


def test_vacation_blend_round_trips_json(tmp_path):
    blend = VacationBlend(
        primary_themes=["road_trip", "adventure_outdoors"],
        secondary_themes=["food_drink"],
        rejected_themes=["nightlife_events"],
        confidence="high",
        evidence=["Many location changes", "Outdoor place names"],
        theme_scores=[
            ThemeScore(
                theme_id="road_trip",
                score=82.5,
                confidence="high",
                evidence=["Travel across 8 cities"],
                sources=["metadata"],
            )
        ],
        analysis_mode="metadata_only",
        sample_size=0,
        estimated_cost=0.0,
        warnings=["Local AI disabled"],
    )

    encoded = encode_vacation_blend(blend)
    decoded = decode_vacation_blend(encoded)

    assert decoded == blend

    path = tmp_path / "vacation_blend.json"
    save_vacation_blend(path, blend)
    loaded = load_vacation_blend(path)

    assert loaded == blend
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'post_trip_summary.discovery'`.

- [ ] **Step 3: Create the discovery package and models**

Create `src/post_trip_summary/discovery/__init__.py`:

```python
"""Vacation Blend Discovery helpers."""

from post_trip_summary.discovery.models import ThemeDefinition, ThemeScore, VacationBlend

__all__ = [
    "ThemeDefinition",
    "ThemeScore",
    "VacationBlend",
]
```

Create `src/post_trip_summary/discovery/models.py`:

```python
"""Dataclasses for Vacation Blend Discovery."""
from __future__ import annotations

from dataclasses import dataclass, field

CONFIDENCE_LEVELS = {"low", "medium", "high"}


@dataclass(frozen=True)
class ThemeDefinition:
    id: str
    label: str
    description: str


@dataclass
class ThemeScore:
    theme_id: str
    score: float
    confidence: str
    evidence: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {self.confidence}")
        self.score = max(0.0, min(100.0, float(self.score)))


@dataclass
class VacationBlend:
    primary_themes: list[str]
    secondary_themes: list[str]
    rejected_themes: list[str]
    confidence: str
    evidence: list[str]
    theme_scores: list[ThemeScore]
    analysis_mode: str
    sample_size: int = 0
    local_model: str | None = None
    cloud_model: str | None = None
    estimated_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {self.confidence}")
```

- [ ] **Step 4: Add the controlled theme taxonomy**

Create `src/post_trip_summary/discovery/taxonomy.py`:

```python
"""Controlled Vacation Blend theme taxonomy."""
from __future__ import annotations

from post_trip_summary.discovery.models import ThemeDefinition

THEMES: tuple[ThemeDefinition, ...] = (
    ThemeDefinition(
        id="road_trip",
        label="Road Trip",
        description="Frequent movement, scenic drives, many stops, changing locations",
    ),
    ThemeDefinition(
        id="adventure_outdoors",
        label="Adventure",
        description="Hiking, boats, viewpoints, rugged terrain, active outdoor travel",
    ),
    ThemeDefinition(
        id="nature_wildlife",
        label="Nature & Wildlife",
        description="Landscapes, animals, parks, gardens, natural features",
    ),
    ThemeDefinition(
        id="culture_sightseeing",
        label="Culture & Sightseeing",
        description="Museums, architecture, historic sites, landmarks, neighborhoods",
    ),
    ThemeDefinition(
        id="food_drink",
        label="Food & Drink",
        description="Restaurants, markets, cafes, wineries, breweries, cooking",
    ),
    ThemeDefinition(
        id="people_social",
        label="People & Friends",
        description="Group photos, friends, family, social moments, portraits",
    ),
    ThemeDefinition(
        id="nightlife_events",
        label="Nightlife & Events",
        description="Clubs, casinos, concerts, shows, evening venues, parties",
    ),
    ThemeDefinition(
        id="beach_relaxation",
        label="Beach & Relaxation",
        description="Beach, pool, sun, slow days, resort downtime",
    ),
    ThemeDefinition(
        id="resort_luxury",
        label="Resort & Luxury",
        description="Hotels, suites, spas, amenities, fine dining, premium experiences",
    ),
    ThemeDefinition(
        id="family_milestone",
        label="Family & Milestones",
        description="Kids, reunions, anniversaries, birthdays, ceremonies",
    ),
)

THEME_BY_ID = {theme.id: theme for theme in THEMES}


def validate_theme_ids(theme_ids: list[str]) -> None:
    unknown = sorted({theme_id for theme_id in theme_ids if theme_id not in THEME_BY_ID})
    if unknown:
        raise ValueError(f"unknown theme id: {', '.join(unknown)}")
```

- [ ] **Step 5: Add JSON serialization helpers**

Create `src/post_trip_summary/discovery/serialization.py`:

```python
"""Serialization helpers for Vacation Blend artifacts."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.taxonomy import validate_theme_ids


def vacation_blend_path(session_dir: Path) -> Path:
    return session_dir / "vacation_blend.json"


def encode_vacation_blend(blend: VacationBlend) -> dict:
    validate_theme_ids(blend.primary_themes)
    validate_theme_ids(blend.secondary_themes)
    validate_theme_ids(blend.rejected_themes)
    validate_theme_ids([score.theme_id for score in blend.theme_scores])
    return asdict(blend)


def decode_vacation_blend(data: dict) -> VacationBlend:
    theme_scores = [
        ThemeScore(
            theme_id=item["theme_id"],
            score=item["score"],
            confidence=item["confidence"],
            evidence=list(item.get("evidence", [])),
            sources=list(item.get("sources", [])),
        )
        for item in data.get("theme_scores", [])
    ]
    blend = VacationBlend(
        primary_themes=list(data.get("primary_themes", [])),
        secondary_themes=list(data.get("secondary_themes", [])),
        rejected_themes=list(data.get("rejected_themes", [])),
        confidence=data.get("confidence", "low"),
        evidence=list(data.get("evidence", [])),
        theme_scores=theme_scores,
        analysis_mode=data.get("analysis_mode", "metadata_only"),
        sample_size=int(data.get("sample_size", 0)),
        local_model=data.get("local_model"),
        cloud_model=data.get("cloud_model"),
        estimated_cost=float(data.get("estimated_cost", 0.0)),
        warnings=list(data.get("warnings", [])),
    )
    encode_vacation_blend(blend)
    return blend


def save_vacation_blend(path: Path, blend: VacationBlend) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(encode_vacation_blend(blend), indent=2),
        encoding="utf-8",
    )


def load_vacation_blend(path: Path) -> VacationBlend:
    return decode_vacation_blend(json.loads(path.read_text(encoding="utf-8")))
```

- [ ] **Step 6: Run tests to verify they pass**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_models.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/post_trip_summary/discovery tests/test_discovery_models.py
git commit -m "Add Vacation Blend discovery models"
```

---

### Task 2: Add Metadata-Only Vacation Blend Scoring

**Files:**
- Create: `src/post_trip_summary/discovery/metadata.py`
- Create: `tests/test_discovery_metadata.py`

- [ ] **Step 1: Write failing metadata discovery tests**

Create `tests/test_discovery_metadata.py`:

```python
from datetime import date, datetime
from pathlib import Path

from post_trip_summary.discovery.metadata import discover_vacation_blend
from post_trip_summary.models import Day, Event, Location, Photo, Trip


def _event(
    event_id: str,
    name: str,
    city: str,
    country: str,
    lat: float,
    lon: float,
    hour: int = 10,
    event_type: str = "activity",
    photo_count: int = 3,
) -> Event:
    photos = [
        Photo(
            path=Path(f"/photos/{event_id}-{idx}.jpg"),
            timestamp=datetime(2026, 3, 1, hour, idx),
            gps=(lat, lon),
            quality_score=80 - idx,
        )
        for idx in range(photo_count)
    ]
    return Event(
        id=event_id,
        type=event_type,
        name=name,
        time_range=(datetime(2026, 3, 1, hour, 0), datetime(2026, 3, 1, hour, 45)),
        location=Location(lat=lat, lon=lon, name=name, address=None, city=city, country=country),
        photos=photos,
        sources=["exif"],
    )


def _trip(events_by_day: list[list[Event]]) -> Trip:
    return Trip(
        name="Test Trip",
        date_range=(date(2026, 3, 1), date(2026, 3, len(events_by_day))),
        days=[
            Day(date=date(2026, 3, idx + 1), events=events)
            for idx, events in enumerate(events_by_day)
        ],
    )


def test_metadata_detects_road_trip_and_adventure():
    trip = _trip([
        [_event("d1e1", "Mountain trail hike", "Auckland", "New Zealand", -36.85, 174.76)],
        [_event("d2e1", "Scenic lake viewpoint", "Rotorua", "New Zealand", -38.14, 176.25)],
        [_event("d3e1", "Alpine park walk", "Taupo", "New Zealand", -38.69, 176.07)],
        [_event("d4e1", "Glacier hiking trail", "Wanaka", "New Zealand", -44.70, 169.13)],
    ])

    blend = discover_vacation_blend(trip)

    assert "road_trip" in blend.primary_themes
    assert "adventure_outdoors" in blend.primary_themes
    assert any("movement" in item.lower() or "cities" in item.lower() for item in blend.evidence)
    assert blend.analysis_mode == "metadata_only"


def test_metadata_detects_beach_and_resort_relaxation():
    trip = _trip([
        [_event("d1e1", "Beach sunset", "Maui", "United States", 20.78, -156.33)],
        [_event("d2e1", "Pool at resort", "Maui", "United States", 20.78, -156.33, event_type="hotel")],
        [_event("d3e1", "Spa morning", "Maui", "United States", 20.78, -156.33, event_type="hotel")],
    ])

    blend = discover_vacation_blend(trip)

    assert "beach_relaxation" in blend.primary_themes
    assert "resort_luxury" in blend.primary_themes or "resort_luxury" in blend.secondary_themes


def test_metadata_detects_food_culture_and_nightlife():
    trip = _trip([
        [_event("d1e1", "Museum of Modern Art", "Las Vegas", "United States", 36.16, -115.14, event_type="landmark")],
        [_event("d1e2", "Tasting menu restaurant", "Las Vegas", "United States", 36.16, -115.15, event_type="restaurant")],
        [_event("d1e3", "Casino club show", "Las Vegas", "United States", 36.17, -115.15, hour=23, event_type="activity")],
    ])

    blend = discover_vacation_blend(trip)

    assert "food_drink" in blend.primary_themes or "food_drink" in blend.secondary_themes
    assert "culture_sightseeing" in blend.primary_themes or "culture_sightseeing" in blend.secondary_themes
    assert "nightlife_events" in blend.primary_themes or "nightlife_events" in blend.secondary_themes


def test_metadata_weak_signal_produces_low_confidence():
    trip = _trip([
        [_event("d1e1", "Unknown", "", "", 0.0, 0.0, photo_count=0, event_type="unknown")],
    ])

    blend = discover_vacation_blend(trip)

    assert blend.primary_themes == []
    assert blend.confidence == "low"
    assert "metadata signal is weak" in " ".join(blend.warnings).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_metadata.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'post_trip_summary.discovery.metadata'`.

- [ ] **Step 3: Implement metadata discovery**

Create `src/post_trip_summary/discovery/metadata.py`:

```python
"""Metadata-only Vacation Blend scoring."""
from __future__ import annotations

import math
from collections import defaultdict

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.taxonomy import THEMES
from post_trip_summary.models import Event, Trip

KEYWORDS: dict[str, tuple[str, ...]] = {
    "road_trip": (
        "drive", "driving", "road", "highway", "scenic", "viewpoint", "overlook",
        "pass", "route", "lookout",
    ),
    "adventure_outdoors": (
        "hike", "hiking", "trail", "walk", "kayak", "boat", "glacier", "alpine",
        "mountain", "cave", "adventure", "track",
    ),
    "nature_wildlife": (
        "park", "lake", "river", "forest", "waterfall", "beach", "wildlife",
        "garden", "zoo", "fjord", "volcano", "island", "mountain",
    ),
    "culture_sightseeing": (
        "museum", "gallery", "historic", "history", "temple", "church",
        "cathedral", "castle", "landmark", "monument", "village", "architecture",
    ),
    "food_drink": (
        "restaurant", "cafe", "coffee", "bar", "market", "winery", "brewery",
        "tasting", "dinner", "lunch", "breakfast", "food",
    ),
    "people_social": (
        "friends", "family", "group", "party", "wedding", "reunion",
    ),
    "nightlife_events": (
        "club", "casino", "show", "concert", "theater", "theatre", "bar",
        "lounge", "night", "party",
    ),
    "beach_relaxation": (
        "beach", "pool", "sunset", "sunrise", "spa", "relax", "relaxation",
        "sand", "ocean", "sea",
    ),
    "resort_luxury": (
        "resort", "hotel", "suite", "spa", "lounge", "fine dining",
        "tasting menu", "villa", "luxury",
    ),
    "family_milestone": (
        "birthday", "anniversary", "wedding", "ceremony", "graduation",
        "reunion", "family",
    ),
}


def discover_vacation_blend(trip: Trip) -> VacationBlend:
    scores: dict[str, float] = {theme.id: 0.0 for theme in THEMES}
    evidence: dict[str, list[str]] = defaultdict(list)
    events = [event for day in trip.days for event in day.events]

    _score_keywords(events, scores, evidence)
    _score_movement(trip, events, scores, evidence)
    _score_time_patterns(events, scores, evidence)
    _score_repeated_relaxation(events, scores, evidence)

    theme_scores = [
        ThemeScore(
            theme_id=theme.id,
            score=round(scores[theme.id], 1),
            confidence=_confidence_for_score(scores[theme.id]),
            evidence=evidence.get(theme.id, []),
            sources=["metadata"] if scores[theme.id] > 0 else [],
        )
        for theme in THEMES
    ]
    ranked = sorted(theme_scores, key=lambda item: item.score, reverse=True)
    primary = [item.theme_id for item in ranked if item.score >= 35][:3]
    secondary = [item.theme_id for item in ranked if 15 <= item.score < 35][:5]
    top_score = ranked[0].score if ranked else 0.0
    overall_confidence = "high" if top_score >= 70 and primary else "medium" if primary else "low"
    top_evidence = [
        line
        for item in ranked
        if item.theme_id in primary
        for line in item.evidence[:2]
    ][:6]
    warnings = []
    if not primary:
        warnings.append("Metadata signal is weak; review and add themes manually.")

    return VacationBlend(
        primary_themes=primary,
        secondary_themes=secondary,
        rejected_themes=[],
        confidence=overall_confidence,
        evidence=top_evidence,
        theme_scores=theme_scores,
        analysis_mode="metadata_only",
        sample_size=0,
        estimated_cost=0.0,
        warnings=warnings,
    )


def _event_text(event: Event) -> str:
    location = event.location
    parts = [
        event.name,
        event.type,
        location.name if location else "",
        location.city if location else "",
        location.country if location else "",
    ]
    return " ".join(part for part in parts if part).lower()


def _score_keywords(events: list[Event], scores: dict[str, float], evidence: dict[str, list[str]]) -> None:
    matched_events: dict[str, set[str]] = defaultdict(set)
    for event in events:
        text = _event_text(event)
        for theme_id, keywords in KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                matched_events[theme_id].add(event.name or event.type)

    for theme_id, names in matched_events.items():
        count = len(names)
        scores[theme_id] += min(50.0, 18.0 * count)
        sample = ", ".join(sorted(names)[:3])
        evidence[theme_id].append(f"{count} event names or places matched {theme_id}: {sample}")


def _score_movement(trip: Trip, events: list[Event], scores: dict[str, float], evidence: dict[str, list[str]]) -> None:
    cities = {
        event.location.city.strip()
        for event in events
        if event.location and event.location.city and event.location.city.strip()
    }
    countries = {
        event.location.country.strip()
        for event in events
        if event.location and event.location.country and event.location.country.strip()
    }
    total_km = _total_movement_km(events)
    day_count = max(1, len(trip.days))

    if len(cities) >= max(3, min(day_count, 5)):
        scores["road_trip"] += 25.0
        evidence["road_trip"].append(f"Trip spans {len(cities)} cities")
    if len(countries) >= 2:
        scores["road_trip"] += 10.0
        evidence["road_trip"].append(f"Trip spans {len(countries)} countries")
    if total_km >= 150:
        scores["road_trip"] += min(35.0, total_km / 12.0)
        evidence["road_trip"].append(f"Approximate event-to-event movement is {round(total_km)} km")


def _score_time_patterns(events: list[Event], scores: dict[str, float], evidence: dict[str, list[str]]) -> None:
    late_events = [
        event
        for event in events
        if event.time_range and (event.time_range[0].hour >= 20 or event.time_range[0].hour <= 3)
    ]
    if len(late_events) >= 2:
        scores["nightlife_events"] += min(20.0, len(late_events) * 6.0)
        evidence["nightlife_events"].append(f"{len(late_events)} evening or late-night events")


def _score_repeated_relaxation(events: list[Event], scores: dict[str, float], evidence: dict[str, list[str]]) -> None:
    city_counts: dict[str, int] = defaultdict(int)
    for event in events:
        if event.location and event.location.city:
            city_counts[event.location.city] += 1
    if not city_counts:
        return
    most_common_city, count = max(city_counts.items(), key=lambda item: item[1])
    if count >= 3 and scores["beach_relaxation"] > 0:
        scores["beach_relaxation"] += 12.0
        evidence["beach_relaxation"].append(f"Repeated relaxed stops around {most_common_city}")


def _total_movement_km(events: list[Event]) -> float:
    coords = [
        (event.location.lat, event.location.lon)
        for event in events
        if event.location and event.location.lat is not None and event.location.lon is not None
    ]
    total = 0.0
    for start, end in zip(coords, coords[1:]):
        total += _haversine_km(start[0], start[1], end[0], end[1])
    return total


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _confidence_for_score(score: float) -> str:
    if score >= 55:
        return "high"
    if score >= 25:
        return "medium"
    if score > 0:
        return "low"
    return "low"
```

- [ ] **Step 4: Run metadata tests to verify they pass**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_metadata.py -v
```

Expected: PASS.

- [ ] **Step 5: Run discovery model and metadata tests together**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_models.py tests/test_discovery_metadata.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/post_trip_summary/discovery tests/test_discovery_metadata.py
git commit -m "Add metadata Vacation Blend discovery"
```

---

### Task 3: Add Session Service, Discovery Stage, and Artifact Persistence

**Files:**
- Create: `src/post_trip_summary/discovery/service.py`
- Create: `tests/test_discovery_service.py`
- Modify: `src/post_trip_summary/config.py`

- [ ] **Step 1: Write failing service and config tests**

Create `tests/test_discovery_service.py`:

```python
from datetime import date, datetime
from pathlib import Path

from post_trip_summary.config import STAGES, create_session, load_session
from post_trip_summary.discovery.serialization import load_vacation_blend, vacation_blend_path
from post_trip_summary.discovery.service import run_discovery_for_session
from post_trip_summary.models import Day, Event, Location, Photo, Trip
from post_trip_summary.serialization import save_trip


def _reviewed_trip() -> Trip:
    photo = Photo(
        path=Path("/photos/trail.jpg"),
        timestamp=datetime(2026, 3, 5, 10, 0),
        gps=(-44.7, 169.1),
        quality_score=90,
    )
    event = Event(
        id="day01-event01",
        type="activity",
        name="Glacier hiking trail",
        time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 12, 0)),
        location=Location(
            lat=-44.7,
            lon=169.1,
            name="Glacier hiking trail",
            address=None,
            city="Wanaka",
            country="New Zealand",
        ),
        photos=[photo],
    )
    return Trip(
        name="New Zealand",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )


def test_discovered_stage_exists_after_reviewed():
    assert STAGES[STAGES.index("reviewed") + 1] == "discovered"


def test_default_settings_include_safe_discovery_defaults(tmp_path):
    session = create_session("Test Trip", base_dir=tmp_path)
    loaded = load_session(session.slug, base_dir=tmp_path)

    assert loaded.settings["discovery"]["mode"] == "metadata_only"
    assert loaded.settings["discovery"]["enable_local_ai"] is False
    assert loaded.settings["discovery"]["enable_cloud_synthesis"] is False


def test_run_discovery_for_session_saves_artifact_and_advances_reviewed_stage(tmp_path):
    session = create_session("New Zealand", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    save_trip(_reviewed_trip(), session.stage_file("reviewed"))

    blend = run_discovery_for_session(session)

    assert "adventure_outdoors" in blend.primary_themes or "adventure_outdoors" in blend.secondary_themes
    assert vacation_blend_path(session.session_dir).exists()
    assert load_vacation_blend(vacation_blend_path(session.session_dir)) == blend
    assert session.current_stage == "discovered"


def test_run_discovery_for_session_does_not_regress_later_stage(tmp_path):
    session = create_session("New Zealand", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    save_trip(_reviewed_trip(), session.stage_file("reviewed"))

    run_discovery_for_session(session)

    assert session.current_stage == "enriched"
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_service.py -v
```

Expected: FAIL because `discovery.service` does not exist and `STAGES` does not include `discovered`.

- [ ] **Step 3: Add discovery defaults and stage**

Modify `src/post_trip_summary/config.py`.

Replace `DEFAULT_SETTINGS` and `STAGES` with:

```python
DEFAULT_SETTINGS = {
    "cluster_time_gap_minutes": 15,
    "cluster_distance_meters": 200,
    "quality_cull_percentile": 15,
    "discovery": {
        "mode": "metadata_only",
        "enable_local_ai": False,
        "local_provider_url": None,
        "local_model": None,
        "enable_cloud_synthesis": False,
        "max_local_images": 150,
        "max_cloud_images": 40,
        "timeout_seconds": 30,
    },
}

STAGES = ["new", "setup", "ingested", "reviewed", "discovered", "enriched", "highlights_done", "generated"]
```

Update `load_session()` so nested discovery defaults are merged:

```python
def _merge_settings(saved: dict | None) -> dict:
    merged = dict(DEFAULT_SETTINGS)
    saved = saved or {}
    for key, value in saved.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            nested = dict(merged[key])
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged
```

Then use it in `load_session()`:

```python
        settings=_merge_settings(data.get("settings", {})),
```

- [ ] **Step 4: Add the discovery service**

Create `src/post_trip_summary/discovery/service.py`:

```python
"""Session orchestration for Vacation Blend Discovery."""
from __future__ import annotations

from post_trip_summary.config import SessionConfig
from post_trip_summary.discovery.metadata import discover_vacation_blend
from post_trip_summary.discovery.models import VacationBlend
from post_trip_summary.discovery.serialization import save_vacation_blend, vacation_blend_path
from post_trip_summary.serialization import load_trip


def run_discovery_for_session(session: SessionConfig, advance_stage: bool = True) -> VacationBlend:
    trip_path = session.stage_file("reviewed")
    if not trip_path.exists():
        raise FileNotFoundError(f"No reviewed trip data found at {trip_path}")

    trip = load_trip(trip_path)
    blend = discover_vacation_blend(trip)
    save_vacation_blend(vacation_blend_path(session.session_dir), blend)

    if advance_stage and session.current_stage == "reviewed":
        session.current_stage = "discovered"
        session.save()

    return blend
```

- [ ] **Step 5: Run service tests to verify they pass**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Run discovery test group**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_models.py tests/test_discovery_metadata.py tests/test_discovery_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/post_trip_summary/config.py src/post_trip_summary/discovery/service.py tests/test_discovery_service.py
git commit -m "Persist Vacation Blend discovery results"
```

---

### Task 4: Add Browser Wizard Discovery Review

**Files:**
- Create: `src/post_trip_summary/templates/discovery.html`
- Modify: `src/post_trip_summary/server/app.py`
- Modify: `src/post_trip_summary/templates/wizard.html`
- Modify: `src/post_trip_summary/templates/review.html`
- Modify: `tests/test_server_app.py`

- [ ] **Step 1: Add failing server tests**

Append to `tests/test_server_app.py`:

```python
def test_reviewed_stage_redirects_to_discovery(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    from post_trip_summary.server.app import create_app

    app = create_app(session)
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert "/wizard/discovery" in response.headers["location"]


def test_discovery_page_renders_and_saves_blend(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    from post_trip_summary.serialization import save_trip
    from post_trip_summary.discovery.serialization import vacation_blend_path
    from post_trip_summary.server.app import create_app, _build_event_index

    trip = _make_test_trip(tmp_path)
    trip.days[0].events[0].name = "Beach resort pool"
    trip.days[0].events[0].location.name = "Beach resort pool"
    save_trip(trip, session.stage_file("reviewed"))
    app = create_app(session)
    app.state.trip = trip
    app.state.event_index = _build_event_index(trip)
    client = TestClient(app)

    response = client.get("/wizard/discovery")

    assert response.status_code == 200
    assert "Trip Discovery" in response.text
    assert "Beach & Relaxation" in response.text
    assert vacation_blend_path(session.session_dir).exists()


def test_discovery_update_saves_user_theme_edits(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    from post_trip_summary.serialization import save_trip
    from post_trip_summary.discovery.serialization import load_vacation_blend, vacation_blend_path
    from post_trip_summary.server.app import create_app, _build_event_index

    trip = _make_test_trip(tmp_path)
    save_trip(trip, session.stage_file("reviewed"))
    app = create_app(session)
    app.state.trip = trip
    app.state.event_index = _build_event_index(trip)
    client = TestClient(app)
    client.get("/wizard/discovery")

    response = client.post("/api/discovery/update", json={
        "primary_themes": ["people_social", "food_drink"],
        "secondary_themes": ["culture_sightseeing"],
    })

    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "discovered"
    assert data["next_step"] == "enrich"
    saved = load_vacation_blend(vacation_blend_path(session.session_dir))
    assert saved.primary_themes == ["people_social", "food_drink"]
    assert saved.secondary_themes == ["culture_sightseeing"]
    assert "road_trip" not in saved.primary_themes
```

- [ ] **Step 2: Run server tests to verify they fail**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_server_app.py -v -k "discovery or reviewed_stage_redirects"
```

Expected: FAIL because the wizard does not have a Discovery route or `discovered` step mapping.

- [ ] **Step 3: Update wizard stage maps**

Modify `src/post_trip_summary/server/app.py`.

Replace the stage maps near the top with:

```python
STAGE_TO_STEP = {
    "new": "setup",
    "setup": "setup",
    "ingested": "review",
    "reviewed": "discovery",
    "discovered": "enrich",
    "enriched": "highlights",
    "highlights_done": "generate",
    "generated": "generate",
}

WIZARD_STEPS = ["setup", "ingest", "review", "discovery", "enrich", "highlights", "generate"]

STEP_COMPLETED_AT = {
    "setup": "ingested",
    "ingest": "ingested",
    "review": "reviewed",
    "discovery": "discovered",
    "enrich": "enriched",
    "highlights": "highlights_done",
    "generate": "generated",
}
```

Update `_load_trip_for_stage()` only if needed after adding `discovered`; its existing `ValueError` catch should let it fall back to the reviewed trip file.

- [ ] **Step 4: Add Discovery route and update endpoint**

In `src/post_trip_summary/server/app.py`, add this route before `wizard_enrich()`:

```python
    @app.get("/wizard/discovery", response_class=HTMLResponse)
    def wizard_discovery():
        if app.state.trip is None:
            return RedirectResponse("/wizard/setup", status_code=307)
        from post_trip_summary.discovery.serialization import load_vacation_blend, vacation_blend_path
        from post_trip_summary.discovery.service import run_discovery_for_session
        from post_trip_summary.discovery.taxonomy import THEMES, THEME_BY_ID

        blend_path = vacation_blend_path(app.state.session.session_dir)
        if blend_path.exists():
            blend = load_vacation_blend(blend_path)
        else:
            blend = run_discovery_for_session(app.state.session, advance_stage=False)

        ctx = _get_wizard_context(app.state.session)
        ctx["blend"] = blend
        ctx["themes"] = THEMES
        ctx["theme_by_id"] = THEME_BY_ID
        template = env.get_template("discovery.html")
        return HTMLResponse(template.render(**ctx))
```

Add this endpoint near other API endpoints:

```python
    @app.post("/api/discovery/update")
    async def update_discovery(request: Request):
        from post_trip_summary.discovery.serialization import (
            load_vacation_blend,
            save_vacation_blend,
            vacation_blend_path,
        )
        from post_trip_summary.discovery.taxonomy import THEME_BY_ID, validate_theme_ids

        body = await request.json()
        primary = list(body.get("primary_themes", []))
        secondary = list(body.get("secondary_themes", []))
        try:
            validate_theme_ids(primary)
            validate_theme_ids(secondary)
        except ValueError as e:
            raise HTTPException(400, str(e))

        duplicate = set(primary) & set(secondary)
        if duplicate:
            raise HTTPException(400, f"theme cannot be both primary and secondary: {', '.join(sorted(duplicate))}")

        blend_path = vacation_blend_path(app.state.session.session_dir)
        if not blend_path.exists():
            raise HTTPException(404, "Vacation Blend has not been generated")
        blend = load_vacation_blend(blend_path)
        previous = set(blend.primary_themes) | set(blend.secondary_themes)
        selected = set(primary) | set(secondary)
        blend.primary_themes = primary
        blend.secondary_themes = secondary
        blend.rejected_themes = sorted((previous - selected) | set(blend.rejected_themes))
        save_vacation_blend(blend_path, blend)

        if app.state.session.current_stage == "reviewed":
            app.state.session.current_stage = "discovered"
            app.state.session.save()

        return JSONResponse({
            "stage": app.state.session.current_stage,
            "next_step": STAGE_TO_STEP.get(app.state.session.current_stage, "enrich"),
            "primary_labels": [THEME_BY_ID[theme_id].label for theme_id in primary],
        })
```

Update `wizard_enrich()` to allow the new stage:

```python
        if app.state.session.current_stage not in ("discovered", "enriched"):
            step = STAGE_TO_STEP.get(app.state.session.current_stage, "setup")
            if step not in ("enrich", "highlights", "generate"):
                return RedirectResponse(f"/wizard/{step}", status_code=307)
```

- [ ] **Step 5: Update wizard nav and review copy**

In `src/post_trip_summary/templates/wizard.html`, update the steps list:

```jinja2
        {% set steps = [
            ("setup", "Setup"),
            ("ingest", "Ingest"),
            ("review", "Review"),
            ("discovery", "Discovery"),
            ("enrich", "Enrich"),
            ("highlights", "Highlights"),
            ("generate", "Generate"),
        ] %}
```

In `src/post_trip_summary/templates/review.html`, change the continue button text:

```html
    <button class="continue-btn" onclick="continueToNext()">Continue to Discovery</button>
```

- [ ] **Step 6: Create the Discovery template**

Create `src/post_trip_summary/templates/discovery.html`:

```html
{% extends "wizard.html" %}
{% block title %}Trip Discovery{% endblock %}

{% block extra_css %}
.discovery-shell { max-width: 760px; margin: 0 auto; }
.discovery-card { background: #16213e; border: 1px solid #0f3460; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.25rem; }
.discovery-card h2 { color: #fff; font-size: 1.1rem; margin-bottom: 0.75rem; }
.theme-group { display: flex; flex-wrap: wrap; gap: 0.6rem; margin: 0.8rem 0 1rem; }
.theme-chip { display: inline-flex; align-items: center; gap: 0.35rem; border: 1px solid #355f8a; background: #0f3460; color: #e0e0e0; border-radius: 999px; padding: 0.45rem 0.75rem; cursor: pointer; font-size: 0.9rem; }
.theme-chip.primary { background: #2ecc71; color: #101827; border-color: #2ecc71; font-weight: 700; }
.theme-chip.secondary { background: #1d4e74; color: #e0e0e0; }
.theme-chip.available { background: transparent; color: #aaa; }
.theme-chip:hover { border-color: #fff; }
.theme-meta { color: #aaa; font-size: 0.92rem; margin-bottom: 1rem; }
.diagnostics { color: #bbb; font-size: 0.86rem; }
.diagnostics summary { cursor: pointer; color: #f4d7a1; margin-bottom: 0.75rem; }
.diagnostics ul { margin-left: 1.2rem; }
.continue-row { text-align: right; margin-top: 1.5rem; }
.error-message { color: #e74c3c; margin-top: 1rem; display: none; }
{% endblock %}

{% block content %}
<div class="discovery-shell">
    <h1>Trip Discovery</h1>
    <h2>This helps the story understand the flavor of the trip before enrichment.</h2>

    <div class="discovery-card">
        <h2>This looks like
            {% if blend.primary_themes %}
                {% for theme_id in blend.primary_themes %}
                    {{ theme_by_id[theme_id].label }}{% if not loop.last %} + {% endif %}
                {% endfor %}
            {% else %}
                a trip that needs your theme selection
            {% endif %}
        </h2>
        <p class="theme-meta">
            Discovery used {{ blend.analysis_mode.replace("_", " ") }} with {{ blend.confidence }} confidence.
        </p>

        <h2>Primary themes</h2>
        <div class="theme-group" id="primary-themes">
            {% for theme_id in blend.primary_themes %}
            <button type="button" class="theme-chip primary" data-theme-id="{{ theme_id }}" onclick="toggleTheme('{{ theme_id }}')">
                {{ theme_by_id[theme_id].label }} ×
            </button>
            {% endfor %}
        </div>

        <h2>Also detected</h2>
        <div class="theme-group" id="secondary-themes">
            {% for theme_id in blend.secondary_themes %}
            <button type="button" class="theme-chip secondary" data-theme-id="{{ theme_id }}" onclick="promoteTheme('{{ theme_id }}')">
                {{ theme_by_id[theme_id].label }} +
            </button>
            {% endfor %}
        </div>

        <h2>Add a theme</h2>
        <div class="theme-group">
            {% for theme in themes %}
                {% if theme.id not in blend.primary_themes and theme.id not in blend.secondary_themes %}
                <button type="button" class="theme-chip available" data-theme-id="{{ theme.id }}" onclick="addPrimaryTheme('{{ theme.id }}')">
                    {{ theme.label }}
                </button>
                {% endif %}
            {% endfor %}
        </div>

        <details class="diagnostics">
            <summary>Development diagnostics</summary>
            <p>Evidence:</p>
            <ul>
                {% for item in blend.evidence %}
                <li>{{ item }}</li>
                {% else %}
                <li>No strong metadata evidence found.</li>
                {% endfor %}
            </ul>
            {% if blend.warnings %}
            <p>Warnings:</p>
            <ul>
                {% for warning in blend.warnings %}
                <li>{{ warning }}</li>
                {% endfor %}
            </ul>
            {% endif %}
        </details>

        <div class="continue-row">
            <button class="btn-primary" onclick="saveDiscovery()">Continue to Enrichment</button>
        </div>
        <div class="error-message" id="error-message"></div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
const themeLabels = {
    {% for theme in themes %}
    "{{ theme.id }}": "{{ theme.label }}"{% if not loop.last %},{% endif %}
    {% endfor %}
};
let primaryThemes = {{ blend.primary_themes | tojson }};
let secondaryThemes = {{ blend.secondary_themes | tojson }};

function renderThemes() {
    const primary = document.getElementById("primary-themes");
    const secondary = document.getElementById("secondary-themes");
    primary.innerHTML = primaryThemes.map(id =>
        `<button type="button" class="theme-chip primary" onclick="toggleTheme('${id}')">${themeLabels[id]} ×</button>`
    ).join("");
    secondary.innerHTML = secondaryThemes.map(id =>
        `<button type="button" class="theme-chip secondary" onclick="promoteTheme('${id}')">${themeLabels[id]} +</button>`
    ).join("");
}

function toggleTheme(themeId) {
    primaryThemes = primaryThemes.filter(id => id !== themeId);
    if (!secondaryThemes.includes(themeId)) {
        secondaryThemes.push(themeId);
    }
    renderThemes();
}

function promoteTheme(themeId) {
    secondaryThemes = secondaryThemes.filter(id => id !== themeId);
    if (!primaryThemes.includes(themeId)) {
        primaryThemes.push(themeId);
    }
    renderThemes();
}

function addPrimaryTheme(themeId) {
    secondaryThemes = secondaryThemes.filter(id => id !== themeId);
    if (!primaryThemes.includes(themeId)) {
        primaryThemes.push(themeId);
    }
    renderThemes();
}

async function saveDiscovery() {
    const error = document.getElementById("error-message");
    error.style.display = "none";
    const resp = await fetch("/api/discovery/update", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            primary_themes: primaryThemes,
            secondary_themes: secondaryThemes,
        })
    });
    if (!resp.ok) {
        const data = await resp.json();
        error.textContent = data.detail || "Failed to save discovery choices";
        error.style.display = "block";
        return;
    }
    const data = await resp.json();
    window.location.href = "/wizard/" + data.next_step;
}
</script>
{% endblock %}
```

- [ ] **Step 7: Run server discovery tests**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_server_app.py -v -k "discovery or reviewed_stage_redirects or enrich_page_renders or advance_stage"
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/post_trip_summary/server/app.py src/post_trip_summary/templates/wizard.html src/post_trip_summary/templates/review.html src/post_trip_summary/templates/discovery.html tests/test_server_app.py
git commit -m "Add Vacation Blend discovery wizard page"
```

---

### Task 5: Add CLI `discover` Command

**Files:**
- Modify: `src/post_trip_summary/cli.py`
- Modify: `tests/test_cli_pipeline.py`

- [ ] **Step 1: Add a failing CLI test**

Append to `tests/test_cli_pipeline.py`:

```python
def test_discover_command_creates_vacation_blend(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    save_trip(_final_trip(tmp_path), session.stage_file("reviewed"))

    result = runner.invoke(cli, ["discover", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "Vacation Blend" in result.output
    assert "Analysis mode: metadata_only" in result.output
    assert (session.session_dir / "vacation_blend.json").exists()
```

- [ ] **Step 2: Run the CLI test to verify it fails**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_cli_pipeline.py::test_discover_command_creates_vacation_blend -v
```

Expected: FAIL because the `discover` command does not exist.

- [ ] **Step 3: Add CLI command**

In `src/post_trip_summary/cli.py`, add this command after `preview()` and before `generate()`:

```python
@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def discover(slug: str, base_dir: Path | None):
    """Run Vacation Blend discovery for a reviewed trip."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    reviewed_file = session.stage_file("reviewed")
    if not reviewed_file.exists():
        click.echo("No reviewed trip data. Run 'resume' and complete timeline review first.")
        raise SystemExit(1)

    from post_trip_summary.discovery.service import run_discovery_for_session
    from post_trip_summary.discovery.taxonomy import THEME_BY_ID

    blend = run_discovery_for_session(session)

    click.echo("\n=== Vacation Blend ===")
    click.echo(f"Analysis mode: {blend.analysis_mode}")
    click.echo(f"Confidence: {blend.confidence}")
    if blend.primary_themes:
        labels = [THEME_BY_ID[theme_id].label for theme_id in blend.primary_themes]
        click.echo("Primary themes: " + ", ".join(labels))
    else:
        click.echo("Primary themes: none detected")
    if blend.secondary_themes:
        labels = [THEME_BY_ID[theme_id].label for theme_id in blend.secondary_themes]
        click.echo("Secondary themes: " + ", ".join(labels))
    if blend.warnings:
        for warning in blend.warnings:
            click.echo(f"Warning: {warning}")
    click.echo(f"Saved to: {session.session_dir / 'vacation_blend.json'}")
```

- [ ] **Step 4: Run CLI test to verify it passes**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_cli_pipeline.py::test_discover_command_creates_vacation_blend -v
```

Expected: PASS.

- [ ] **Step 5: Run CLI pipeline tests**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_cli_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/post_trip_summary/cli.py tests/test_cli_pipeline.py
git commit -m "Add Vacation Blend discover command"
```

---

### Task 6: Update README and Run Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README pipeline stage table**

In `README.md`, update the pipeline stage list so Discovery appears between Review and Enrich:

```markdown
| **Discovery** | Detects the Vacation Blend themes, such as Road Trip, Adventure, Food & Drink, or Beach & Relaxation |
```

- [ ] **Step 2: Update README command list**

Add the command to the CLI section:

```markdown
post-trip-summary discover <slug>         Run Vacation Blend discovery after timeline review
```

- [ ] **Step 3: Run documentation diff check**

Run:

```powershell
git diff --check -- README.md
```

Expected: no output and exit code 0.

- [ ] **Step 4: Commit README update**

```powershell
git add README.md
git commit -m "Document Vacation Blend discovery"
```

- [ ] **Step 5: Run focused discovery tests**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_discovery_models.py tests/test_discovery_metadata.py tests/test_discovery_service.py -v
```

Expected: PASS.

- [ ] **Step 6: Run focused wizard and CLI tests**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests/test_server_app.py tests/test_cli_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 7: Run full test suite**

Run:

```powershell
..\..\.venv\Scripts\python.exe -m pytest -q
```

Expected: all tests pass. The existing unregistered `pytest.mark.integration` warning in `tests/test_overpass.py` is acceptable if it remains the only warning.

- [ ] **Step 8: Inspect final git state**

Run:

```powershell
git status --short
git log --oneline --decorate -8
```

Expected: clean worktree and recent commits for the Vacation Blend implementation tasks.

---

## Manual Smoke Test

After full verification passes, try this against an existing reviewed session:

```powershell
..\..\.venv\Scripts\post-trip-summary.exe discover <slug>
..\..\.venv\Scripts\post-trip-summary.exe start <slug>
```

Expected:

- `vacation_blend.json` is written to the session directory.
- The CLI reports analysis mode, confidence, and primary/secondary themes.
- A reviewed session opens to `/wizard/discovery`.
- The Discovery page shows primary and secondary theme chips.
- Removing/promoting/adding chips and continuing saves the accepted blend.
- Continuing from Discovery sends the user to Enrichment.
- Existing enrichment, highlights, generate, and Trip Story behavior still work.
