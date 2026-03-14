# Post-Trip Summary Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that processes vacation photos and trip data to produce a detailed personal trip record and a shareable summary.

**Architecture:** A staged pipeline CLI app. Each stage reads the previous stage's JSON output, processes data, and writes its own output. Two interactive review stages pause for user input. Output generators use Jinja2 templates rendered to HTML/PDF.

**Tech Stack:** Python 3.10+, click (CLI), PyExifTool (EXIF), Pillow/pillow-heif (images), imagehash (dedup), reverse_geocoder/geopy (geo), openpyxl (Excel), anthropic (Claude Vision), WeasyPrint (PDF), FastAPI (preview), Jinja2 (templates)

**Spec:** `docs/superpowers/specs/2026-03-13-post-trip-summary-design.md`

---

## Chunk 1: Project Foundation — Setup, Models, Config, CLI Skeleton

### Task 1: Project scaffolding and dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/post_trip_summary/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "post-trip-summary"
version = "0.1.0"
description = "Generate trip summaries from vacation photos and travel data"
requires-python = ">=3.10"
dependencies = [
    "click>=8.1",
    "Pillow>=10.0",
    "pillow-heif>=0.13",
    "PyExifTool>=0.5",
    "imagehash>=4.3",
    "reverse_geocoder>=1.5",
    "geopy>=2.4",
    "openpyxl>=3.1",
    "anthropic>=0.40",
    "weasyprint>=62.0",
    "Jinja2>=3.1",
    "fastapi>=0.115",
    "uvicorn>=0.32",
    "staticmap>=0.5",
]

[project.scripts]
post-trip-summary = "post_trip_summary.cli:cli"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create requirements.txt**

```
click>=8.1
Pillow>=10.0
pillow-heif>=0.13
PyExifTool>=0.5
imagehash>=4.3
reverse_geocoder>=1.5
geopy>=2.4
openpyxl>=3.1
anthropic>=0.40
weasyprint>=62.0
Jinja2>=3.1
fastapi>=0.115
uvicorn>=0.32
staticmap>=0.5
pytest>=8.0
```

- [ ] **Step 3: Create package init**

```python
# src/post_trip_summary/__init__.py
"""Post-Trip Summary: Generate trip summaries from vacation photos and travel data."""
__version__ = "0.1.0"
```

- [ ] **Step 4: Create virtual environment, install, and set up test directory**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && python -m venv .venv && .venv/Scripts/activate && pip install -e . && pip install pytest>=8.0 && mkdir -p tests`
Expected: Successfully installed post-trip-summary and dependencies, tests/ directory created

- [ ] **Step 5: Initialize git and commit**

```bash
git init
echo ".venv/" > .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo ".superpowers/" >> .gitignore
git add pyproject.toml requirements.txt src/post_trip_summary/__init__.py .gitignore
git commit -m "feat: initial project scaffolding with dependencies"
```

---

### Task 2: Data models

**Files:**
- Create: `src/post_trip_summary/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test for model creation**

```python
# tests/test_models.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Transit, TransitPoint,
    Accommodation, Expense,
)


def test_create_location():
    loc = Location(lat=48.8584, lon=2.2945, name="Eiffel Tower", address="5 Av. Anatole France", city="Paris", country="France")
    assert loc.name == "Eiffel Tower"
    assert loc.lat == 48.8584


def test_create_photo():
    photo = Photo(path=Path("/photos/img001.jpg"), timestamp=datetime(2026, 3, 5, 14, 30), gps=(48.8584, 2.2945), is_highlight=False, ai_description=None)
    assert photo.gps == (48.8584, 2.2945)
    assert photo.is_highlight is False


def test_create_event():
    loc = Location(lat=48.8584, lon=2.2945, name="Eiffel Tower", address=None, city="Paris", country="France")
    event = Event(
        id="day01-event01",
        type="landmark",
        name="Eiffel Tower",
        time_range=(datetime(2026, 3, 5, 16, 15), datetime(2026, 3, 5, 18, 0)),
        location=loc,
        photos=[],
        description="Visit to the Eiffel Tower",
        notes="",
        sources=["exif", "itinerary"],
    )
    assert event.id == "day01-event01"
    assert event.type == "landmark"
    assert len(event.sources) == 2


def test_create_transit():
    dep = TransitPoint(
        location=Location(lat=49.0097, lon=2.5479, name="CDG", address=None, city="Paris", country="France"),
        time=datetime(2026, 3, 5, 14, 0),
        name="CDG Terminal 2",
    )
    arr = TransitPoint(
        location=Location(lat=48.8566, lon=2.3522, name="Hotel", address=None, city="Paris", country="France"),
        time=datetime(2026, 3, 5, 15, 30),
        name="Hotel Le Marais",
    )
    transit = Transit(mode="taxi", departure=dep, arrival=arr, details={"cost": "€55"}, sources=["itinerary"])
    assert transit.mode == "taxi"


def test_create_expense():
    exp = Expense(date=date(2026, 3, 5), amount=87.50, currency="EUR", merchant="REST LE PETIT", category="dining", event_id="day01-event04", source="credit_card")
    assert exp.amount == 87.50
    assert exp.event_id == "day01-event04"


def test_create_trip():
    trip = Trip(name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 12)), days=[], accommodations=[], transits=[], expenses=[])
    assert trip.name == "Paris 2026"
    assert trip.days == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: FAIL — cannot import `post_trip_summary.models`

- [ ] **Step 3: Implement models**

```python
# src/post_trip_summary/models.py
"""Core data models for trip representation."""
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class Location:
    lat: float
    lon: float
    name: str
    address: str | None
    city: str
    country: str


@dataclass
class Photo:
    path: Path
    timestamp: datetime
    gps: tuple[float, float] | None
    is_highlight: bool = False
    ai_description: str | None = None


@dataclass
class Event:
    id: str
    type: str  # landmark, restaurant, hotel, activity, transit, unknown
    name: str
    time_range: tuple[datetime, datetime]
    location: Location
    photos: list[Photo] = field(default_factory=list)
    description: str = ""
    notes: str = ""
    sources: list[str] = field(default_factory=list)


@dataclass
class Day:
    date: date
    events: list[Event] = field(default_factory=list)


@dataclass
class TransitPoint:
    location: Location
    time: datetime
    name: str


@dataclass
class Transit:
    mode: str  # flight, car_rental, train, ferry, bus, taxi, walking
    departure: TransitPoint
    arrival: TransitPoint
    details: dict = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)


@dataclass
class Accommodation:
    name: str
    location: Location
    check_in: date
    check_out: date
    sources: list[str] = field(default_factory=list)


@dataclass
class Expense:
    date: date
    amount: float
    currency: str
    merchant: str
    category: str | None = None
    event_id: str | None = None
    source: str = ""


@dataclass
class Trip:
    name: str
    date_range: tuple[date, date]
    days: list[Day] = field(default_factory=list)
    accommodations: list[Accommodation] = field(default_factory=list)
    transits: list[Transit] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/models.py tests/test_models.py
git commit -m "feat: add core data models (Trip, Event, Photo, Location, Transit, etc.)"
```

---

### Task 3: Model serialization (JSON persistence)

**Files:**
- Create: `src/post_trip_summary/serialization.py`
- Create: `tests/test_serialization.py`

- [ ] **Step 1: Write failing test for round-trip serialization**

```python
# tests/test_serialization.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Transit, TransitPoint,
    Accommodation, Expense,
)
from post_trip_summary.serialization import trip_to_json, trip_from_json


def _make_sample_trip() -> Trip:
    loc = Location(lat=48.8584, lon=2.2945, name="Eiffel Tower", address=None, city="Paris", country="France")
    photo = Photo(path=Path("/photos/img001.jpg"), timestamp=datetime(2026, 3, 5, 16, 30), gps=(48.8584, 2.2945), is_highlight=True, ai_description="Family at Eiffel Tower")
    event = Event(id="day01-event01", type="landmark", name="Eiffel Tower", time_range=(datetime(2026, 3, 5, 16, 15), datetime(2026, 3, 5, 18, 0)), location=loc, photos=[photo], description="Visit", notes="Great view", sources=["exif"])
    day = Day(date=date(2026, 3, 5), events=[event])
    dep_loc = Location(lat=49.0, lon=2.5, name="CDG", address=None, city="Paris", country="France")
    arr_loc = Location(lat=48.8, lon=2.3, name="Hotel", address="123 Rue", city="Paris", country="France")
    transit = Transit(mode="taxi", departure=TransitPoint(location=dep_loc, time=datetime(2026, 3, 5, 14, 0), name="CDG T2"), arrival=TransitPoint(location=arr_loc, time=datetime(2026, 3, 5, 15, 0), name="Hotel"), details={"cost": 55}, sources=["itinerary"])
    accom = Accommodation(name="Hotel Le Marais", location=arr_loc, check_in=date(2026, 3, 5), check_out=date(2026, 3, 8), sources=["itinerary"])
    expense = Expense(date=date(2026, 3, 5), amount=87.5, currency="EUR", merchant="REST LE PETIT", category="dining", event_id="day01-event04", source="credit_card")
    return Trip(name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 12)), days=[day], accommodations=[accom], transits=[transit], expenses=[expense])


def test_round_trip_serialization():
    trip = _make_sample_trip()
    json_str = trip_to_json(trip)
    restored = trip_from_json(json_str)
    assert restored.name == trip.name
    assert restored.date_range == trip.date_range
    assert len(restored.days) == 1
    assert len(restored.days[0].events) == 1
    assert restored.days[0].events[0].id == "day01-event01"
    assert restored.days[0].events[0].photos[0].gps == (48.8584, 2.2945)
    assert restored.days[0].events[0].photos[0].path == Path("/photos/img001.jpg")
    assert len(restored.transits) == 1
    assert restored.transits[0].mode == "taxi"
    assert len(restored.accommodations) == 1
    assert len(restored.expenses) == 1
    assert restored.expenses[0].amount == 87.5


def test_serialization_to_file(tmp_path):
    from post_trip_summary.serialization import save_trip, load_trip
    trip = _make_sample_trip()
    path = tmp_path / "trip.json"
    save_trip(trip, path)
    assert path.exists()
    restored = load_trip(path)
    assert restored.name == "Paris 2026"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_serialization.py -v`
Expected: FAIL — cannot import `serialization`

- [ ] **Step 3: Implement serialization**

```python
# src/post_trip_summary/serialization.py
"""JSON serialization for Trip model tree."""
import json
from datetime import date, datetime
from pathlib import Path

from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Transit, TransitPoint,
    Accommodation, Expense,
)


def _encode(obj: object) -> object:
    """Recursively convert model tree to JSON-safe dicts."""
    if isinstance(obj, datetime):
        return {"__type__": "datetime", "value": obj.isoformat()}
    if isinstance(obj, date):
        return {"__type__": "date", "value": obj.isoformat()}
    if isinstance(obj, Path):
        return {"__type__": "Path", "value": str(obj)}
    if isinstance(obj, tuple):
        return {"__type__": "tuple", "value": [_encode(v) for v in obj]}
    if isinstance(obj, list):
        return [_encode(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        return {
            "__type__": type(obj).__name__,
            **{k: _encode(v) for k, v in obj.__dict__.items()},
        }
    return obj


_MODEL_MAP = {
    "Trip": Trip,
    "Day": Day,
    "Event": Event,
    "Photo": Photo,
    "Location": Location,
    "Transit": Transit,
    "TransitPoint": TransitPoint,
    "Accommodation": Accommodation,
    "Expense": Expense,
}


def _decode(obj: object) -> object:
    """Recursively restore model tree from JSON-safe dicts."""
    if isinstance(obj, list):
        return [_decode(v) for v in obj]
    if not isinstance(obj, dict):
        return obj
    type_tag = obj.get("__type__")
    if type_tag == "datetime":
        return datetime.fromisoformat(obj["value"])
    if type_tag == "date":
        return date.fromisoformat(obj["value"])
    if type_tag == "Path":
        return Path(obj["value"])
    if type_tag == "tuple":
        return tuple(_decode(v) for v in obj["value"])
    if type_tag in _MODEL_MAP:
        cls = _MODEL_MAP[type_tag]
        fields = {k: _decode(v) for k, v in obj.items() if k != "__type__"}
        return cls(**fields)
    return {k: _decode(v) for k, v in obj.items()}


# Public API for encoding/decoding arbitrary values (used by CLI for trip_data dict)
encode_value = _encode
decode_value = _decode


def trip_to_json(trip: Trip) -> str:
    return json.dumps(_encode(trip), indent=2)


def trip_from_json(json_str: str) -> Trip:
    return _decode(json.loads(json_str))


def save_trip(trip: Trip, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(trip_to_json(trip), encoding="utf-8")


def load_trip(path: Path) -> Trip:
    return trip_from_json(path.read_text(encoding="utf-8"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_serialization.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/serialization.py tests/test_serialization.py
git commit -m "feat: add JSON serialization for Trip model tree"
```

---

### Task 4: Session config and management

**Files:**
- Create: `src/post_trip_summary/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for session management**

```python
# tests/test_config.py
import json
from post_trip_summary.config import SessionConfig, create_session, load_session, list_sessions, delete_session


def test_create_session(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    assert session.name == "Paris 2026"
    assert session.slug == "paris-2026"
    assert session.session_dir.exists()
    assert (session.session_dir / "config.json").exists()


def test_create_session_with_inputs(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.inputs["photos"] = "/path/to/photos"
    session.inputs["excel"] = "/path/to/itinerary.xlsx"
    session.save()
    loaded = load_session("paris-2026", base_dir=tmp_path)
    assert loaded.inputs["photos"] == "/path/to/photos"
    assert loaded.inputs["excel"] == "/path/to/itinerary.xlsx"


def test_load_session(tmp_path):
    create_session("Paris 2026", base_dir=tmp_path)
    loaded = load_session("paris-2026", base_dir=tmp_path)
    assert loaded.name == "Paris 2026"


def test_list_sessions(tmp_path):
    create_session("Paris 2026", base_dir=tmp_path)
    create_session("NZ 2025", base_dir=tmp_path)
    sessions = list_sessions(base_dir=tmp_path)
    assert len(sessions) == 2
    slugs = {s.slug for s in sessions}
    assert slugs == {"paris-2026", "nz-2025"}


def test_delete_session(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    assert session.session_dir.exists()
    delete_session("paris-2026", base_dir=tmp_path)
    assert not session.session_dir.exists()


def test_current_stage_tracking(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    assert session.current_stage == "new"
    session.current_stage = "ingest"
    session.save()
    loaded = load_session("paris-2026", base_dir=tmp_path)
    assert loaded.current_stage == "ingest"


def test_config_settings_defaults(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    assert session.settings["cluster_time_gap_minutes"] == 15
    assert session.settings["cluster_distance_meters"] == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL — cannot import `config`

- [ ] **Step 3: Implement config**

```python
# src/post_trip_summary/config.py
"""Session configuration and management."""
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_DIR = Path.home() / ".post-trip-summary" / "sessions"

DEFAULT_SETTINGS = {
    "cluster_time_gap_minutes": 15,
    "cluster_distance_meters": 200,
}

STAGES = ["new", "ingest", "skeleton", "skeleton_reviewed", "enriched", "final", "generated"]


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")


@dataclass
class SessionConfig:
    name: str
    slug: str
    session_dir: Path
    current_stage: str = "new"
    inputs: dict = field(default_factory=dict)
    settings: dict = field(default_factory=lambda: dict(DEFAULT_SETTINGS))

    def save(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "slug": self.slug,
            "current_stage": self.current_stage,
            "inputs": self.inputs,
            "settings": self.settings,
        }
        config_path = self.session_dir / "config.json"
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def stage_file(self, stage: str) -> Path:
        filenames = {
            "ingest": "trip_data.json",
            "skeleton": "trip_skeleton.json",
            "skeleton_reviewed": "trip_skeleton_reviewed.json",
            "enriched": "trip_enriched.json",
            "final": "trip_final.json",
        }
        return self.session_dir / filenames[stage]

    @property
    def output_dir(self) -> Path:
        return self.session_dir / "output"


def create_session(name: str, base_dir: Path | None = None) -> SessionConfig:
    base = base_dir or DEFAULT_BASE_DIR
    slug = _slugify(name)
    session_dir = base / slug
    session = SessionConfig(name=name, slug=slug, session_dir=session_dir)
    session.save()
    return session


def load_session(slug: str, base_dir: Path | None = None) -> SessionConfig:
    base = base_dir or DEFAULT_BASE_DIR
    config_path = base / slug / "config.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return SessionConfig(
        name=data["name"],
        slug=data["slug"],
        session_dir=base / slug,
        current_stage=data.get("current_stage", "new"),
        inputs=data.get("inputs", {}),
        settings={**DEFAULT_SETTINGS, **data.get("settings", {})},
    )


def list_sessions(base_dir: Path | None = None) -> list[SessionConfig]:
    base = base_dir or DEFAULT_BASE_DIR
    if not base.exists():
        return []
    sessions = []
    for child in sorted(base.iterdir()):
        config_path = child / "config.json"
        if config_path.exists():
            sessions.append(load_session(child.name, base_dir=base))
    return sessions


def delete_session(slug: str, base_dir: Path | None = None) -> None:
    base = base_dir or DEFAULT_BASE_DIR
    session_dir = base / slug
    if session_dir.exists():
        shutil.rmtree(session_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/config.py tests/test_config.py
git commit -m "feat: add session config management (create, load, list, delete)"
```

---

### Task 5: CLI skeleton with click

**Files:**
- Create: `src/post_trip_summary/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for CLI commands**

```python
# tests/test_cli.py
from click.testing import CliRunner
from post_trip_summary.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Post-Trip Summary" in result.output


def test_new_command(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["new", "Paris 2026", "--base-dir", str(tmp_path)], input="/fake/photos\n")
    assert result.exit_code == 0
    assert "Created session" in result.output


def test_list_command_empty(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--base-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "No sessions" in result.output


def test_list_command_with_sessions(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["new", "Paris 2026", "--base-dir", str(tmp_path)], input="/fake/photos\n")
    result = runner.invoke(cli, ["list", "--base-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "paris-2026" in result.output


def test_delete_command(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["new", "Paris 2026", "--base-dir", str(tmp_path)], input="/fake/photos\n")
    result = runner.invoke(cli, ["delete", "paris-2026", "--base-dir", str(tmp_path)], input="y\n")
    assert result.exit_code == 0
    assert "Deleted" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: FAIL — cannot import `cli`

- [ ] **Step 3: Implement CLI skeleton**

```python
# src/post_trip_summary/cli.py
"""CLI entry point for Post-Trip Summary."""
import click
from pathlib import Path

from post_trip_summary.config import (
    create_session, load_session, list_sessions, delete_session, DEFAULT_BASE_DIR,
)


@click.group()
@click.version_option()
def cli():
    """Post-Trip Summary — Generate trip summaries from vacation photos and travel data."""
    pass


@cli.command()
@click.argument("name")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def new(name: str, base_dir: Path | None):
    """Create a new trip session."""
    base = base_dir or DEFAULT_BASE_DIR
    session = create_session(name, base_dir=base)
    click.echo(f"Created session '{session.name}' ({session.slug})")
    photos_path = click.prompt("Where are your photos?", type=str)
    session.inputs["photos"] = photos_path
    session.save()
    click.echo(f"Session saved. Run 'post-trip-summary resume {session.slug}' to continue.")


@cli.command("list")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def list_cmd(base_dir: Path | None):
    """List all trip sessions."""
    base = base_dir or DEFAULT_BASE_DIR
    sessions = list_sessions(base_dir=base)
    if not sessions:
        click.echo("No sessions found.")
        return
    for s in sessions:
        click.echo(f"  {s.slug}  ({s.name})  stage: {s.current_stage}")


@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def delete(slug: str, base_dir: Path | None):
    """Delete a trip session."""
    base = base_dir or DEFAULT_BASE_DIR
    if click.confirm(f"Delete session '{slug}'? This cannot be undone"):
        delete_session(slug, base_dir=base)
        click.echo(f"Deleted session '{slug}'.")


@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def resume(slug: str, base_dir: Path | None):
    """Resume a trip session from where you left off."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    click.echo(f"Resuming '{session.name}' at stage: {session.current_stage}")
    # STUB: Pipeline stages will be wired in Chunk 6, Task 24. This is intentionally incomplete.


@cli.command("add-input")
@click.argument("slug")
@click.option("--photos", type=click.Path(exists=True, path_type=Path))
@click.option("--excel", type=click.Path(exists=True, path_type=Path))
@click.option("--credit-card", type=click.Path(exists=True, path_type=Path))
@click.option("--google-maps", type=click.Path(exists=True, path_type=Path))
@click.option("--apple-health", type=click.Path(exists=True, path_type=Path))
@click.option("--dayone", type=click.Path(exists=True, path_type=Path))
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def add_input(slug: str, base_dir: Path | None, **inputs):
    """Add input data sources to a session."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    for key, value in inputs.items():
        if key == "base_dir":
            continue
        if value is not None:
            session.inputs[key.replace("-", "_")] = str(value)
            click.echo(f"  Added {key}: {value}")
    session.save()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/cli.py tests/test_cli.py
git commit -m "feat: add CLI skeleton with new, list, delete, resume, add-input commands"
```

---

## Chunk 2: Stage 1 — Ingest Pipeline

### Task 6: Photo EXIF extraction

**Files:**
- Create: `src/post_trip_summary/pipeline/__init__.py`
- Create: `src/post_trip_summary/pipeline/ingest/__init__.py`
- Create: `src/post_trip_summary/pipeline/ingest/photos.py`
- Create: `tests/test_ingest_photos.py`

- [ ] **Step 1: Create pipeline package init files**

```python
# src/post_trip_summary/pipeline/__init__.py
# src/post_trip_summary/pipeline/ingest/__init__.py
```

Both are empty init files.

- [ ] **Step 2: Write failing test for photo scanning**

```python
# tests/test_ingest_photos.py
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
from post_trip_summary.pipeline.ingest.photos import scan_photos, extract_photo_metadata, SUPPORTED_EXTENSIONS


def test_supported_extensions():
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".heic" in SUPPORTED_EXTENSIONS
    assert ".mp4" not in SUPPORTED_EXTENSIONS


def test_extract_photo_metadata_with_gps():
    """Test extraction when EXIF data has GPS and DateTimeOriginal."""
    mock_tags = {
        "EXIF:DateTimeOriginal": "2026:03:05 16:30:00",
        "EXIF:GPSLatitude": 48.8584,
        "EXIF:GPSLongitude": 2.2945,
        "EXIF:GPSLatitudeRef": "N",
        "EXIF:GPSLongitudeRef": "E",
    }
    result = extract_photo_metadata(Path("/photos/img001.jpg"), mock_tags)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)
    assert result.gps is not None
    assert abs(result.gps[0] - 48.8584) < 0.001
    assert abs(result.gps[1] - 2.2945) < 0.001


def test_extract_photo_metadata_no_gps():
    """Test extraction when EXIF data has date but no GPS."""
    mock_tags = {
        "EXIF:DateTimeOriginal": "2026:03:05 16:30:00",
    }
    result = extract_photo_metadata(Path("/photos/img002.jpg"), mock_tags)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)
    assert result.gps is None


def test_extract_photo_metadata_date_fallback():
    """Test date cascade: CreateDate when DateTimeOriginal missing."""
    mock_tags = {
        "EXIF:CreateDate": "2026:03:05 16:30:00",
    }
    result = extract_photo_metadata(Path("/photos/img003.jpg"), mock_tags)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)


def test_extract_photo_metadata_filename_fallback():
    """Test date from filename pattern when no EXIF date."""
    mock_tags = {}
    result = extract_photo_metadata(Path("/photos/IMG_20260305_163000.jpg"), mock_tags)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)


def test_extract_photo_metadata_south_west_gps():
    """Test GPS with south latitude and west longitude."""
    mock_tags = {
        "EXIF:DateTimeOriginal": "2026:03:05 10:00:00",
        "EXIF:GPSLatitude": 37.7749,
        "EXIF:GPSLongitude": 122.4194,
        "EXIF:GPSLatitudeRef": "S",
        "EXIF:GPSLongitudeRef": "W",
    }
    result = extract_photo_metadata(Path("/photos/img004.jpg"), mock_tags)
    assert result.gps[0] < 0  # South
    assert result.gps[1] < 0  # West


def test_scan_photos(tmp_path):
    """Test scanning a directory with mixed files."""
    (tmp_path / "photo1.jpg").write_text("fake")
    (tmp_path / "photo2.heic").write_text("fake")
    (tmp_path / "video.mp4").write_text("fake")
    (tmp_path / "notes.txt").write_text("fake")
    sub = tmp_path / "subfolder"
    sub.mkdir()
    (sub / "photo3.png").write_text("fake")

    found = scan_photos(tmp_path)
    extensions = {p.suffix.lower() for p in found}
    assert len(found) == 3
    assert ".mp4" not in extensions
    assert ".txt" not in extensions
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_photos.py -v`
Expected: FAIL — cannot import `pipeline.ingest.photos`

- [ ] **Step 4: Implement photo ingest**

```python
# src/post_trip_summary/pipeline/ingest/photos.py
"""EXIF extraction and photo scanning."""
import re
from datetime import datetime
from pathlib import Path

from post_trip_summary.models import Photo

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".webp"}

# EXIF date tags in priority order (cascade)
_DATE_TAGS = [
    "EXIF:DateTimeOriginal",
    "RIFF:DateTimeOriginal",
    "QuickTime:CreateDate",
    "Composite:GPSDateTime",
    "EXIF:CreateDate",
]

_EXIF_DATE_FMT = "%Y:%m:%d %H:%M:%S"
_FILENAME_PATTERN = re.compile(r"IMG_(\d{8})_(\d{6})")


def scan_photos(directory: Path) -> list[Path]:
    """Recursively find all supported image files in directory."""
    photos = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            photos.append(path)
    return photos


def _parse_exif_date(value: str) -> datetime | None:
    """Parse an EXIF date string."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), _EXIF_DATE_FMT)
    except (ValueError, TypeError):
        return None


def _parse_filename_date(path: Path) -> datetime | None:
    """Try to extract date from filename pattern IMG_YYYYMMDD_HHMMSS."""
    match = _FILENAME_PATTERN.search(path.stem)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)}_{match.group(2)}", "%Y%m%d_%H%M%S")
        except ValueError:
            return None
    return None


def _extract_timestamp(path: Path, tags: dict) -> datetime | None:
    """Resolve timestamp using date cascade, falling back to filename."""
    for tag in _DATE_TAGS:
        if tag in tags:
            dt = _parse_exif_date(tags[tag])
            if dt:
                return dt
    return _parse_filename_date(path)


def _extract_gps(tags: dict) -> tuple[float, float] | None:
    """Extract GPS coordinates, applying S/W sign convention."""
    lat = tags.get("EXIF:GPSLatitude")
    lon = tags.get("EXIF:GPSLongitude")
    if lat is None or lon is None:
        return None
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return None
    lat_ref = tags.get("EXIF:GPSLatitudeRef", "N")
    lon_ref = tags.get("EXIF:GPSLongitudeRef", "E")
    if lat_ref == "S":
        lat = -abs(lat)
    if lon_ref == "W":
        lon = -abs(lon)
    return (lat, lon)


def extract_photo_metadata(path: Path, tags: dict) -> Photo:
    """Build a Photo model from a file path and its EXIF tags."""
    timestamp = _extract_timestamp(path, tags)
    gps = _extract_gps(tags)
    return Photo(
        path=path,
        timestamp=timestamp or datetime.min,
        gps=gps,
    )


def ingest_photos(directory: Path) -> list[Photo]:
    """Scan directory and extract metadata from all photos using exiftool."""
    import exiftool

    paths = scan_photos(directory)
    if not paths:
        return []

    photos = []
    batch_size = 50
    with exiftool.ExifToolHelper() as et:
        for i in range(0, len(paths), batch_size):
            batch = paths[i : i + batch_size]
            str_paths = [str(p) for p in batch]
            all_tags = et.get_tags(str_paths, _DATE_TAGS + [
                "EXIF:GPSLatitude", "EXIF:GPSLongitude",
                "EXIF:GPSLatitudeRef", "EXIF:GPSLongitudeRef",
            ])
            for path, tags in zip(batch, all_tags):
                photos.append(extract_photo_metadata(path, tags))

    return sorted(photos, key=lambda p: p.timestamp)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_photos.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/post_trip_summary/pipeline/__init__.py src/post_trip_summary/pipeline/ingest/__init__.py src/post_trip_summary/pipeline/ingest/photos.py tests/test_ingest_photos.py
git commit -m "feat: add photo EXIF extraction with date cascade and GPS parsing"
```

---

### Task 7: Excel workbook ingest

**Files:**
- Create: `src/post_trip_summary/pipeline/ingest/excel.py`
- Create: `tests/test_ingest_excel.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingest_excel.py
from datetime import date, datetime
from pathlib import Path
from openpyxl import Workbook
from post_trip_summary.pipeline.ingest.excel import ingest_excel


def _create_test_workbook(path: Path) -> None:
    """Create a minimal test workbook with accommodations, transit, activities, expenses tabs."""
    wb = Workbook()

    # Accommodations tab
    ws_acc = wb.active
    ws_acc.title = "Accommodations"
    ws_acc.append(["Name", "Address", "City", "Country", "Check-In", "Check-Out"])
    ws_acc.append(["Hotel Le Marais", "123 Rue de Rivoli", "Paris", "France", "2026-03-05", "2026-03-08"])

    # Transit tab
    ws_transit = wb.create_sheet("Transit")
    ws_transit.append(["Mode", "From", "To", "Departure", "Arrival", "Details"])
    ws_transit.append(["flight", "JFK", "CDG", "2026-03-05 08:00", "2026-03-05 14:00", "AF001"])

    # Activities tab
    ws_act = wb.create_sheet("Activities")
    ws_act.append(["Name", "Location", "City", "Country", "Date", "Time", "Notes"])
    ws_act.append(["Seine River Cruise", "Port de la Bourdonnais", "Paris", "France", "2026-03-06", "19:00", "Reservation #12345"])

    # Expenses tab
    ws_exp = wb.create_sheet("Expenses")
    ws_exp.append(["Date", "Amount", "Currency", "Merchant", "Category"])
    ws_exp.append(["2026-03-05", 87.50, "EUR", "REST LE PETIT", "dining"])

    wb.save(path)


def test_ingest_accommodations(tmp_path):
    wb_path = tmp_path / "trip.xlsx"
    _create_test_workbook(wb_path)
    result = ingest_excel(wb_path)
    assert len(result["accommodations"]) == 1
    acc = result["accommodations"][0]
    assert acc.name == "Hotel Le Marais"
    assert acc.check_in == date(2026, 3, 5)


def test_ingest_transit(tmp_path):
    wb_path = tmp_path / "trip.xlsx"
    _create_test_workbook(wb_path)
    result = ingest_excel(wb_path)
    assert len(result["transits"]) == 1
    t = result["transits"][0]
    assert t.mode == "flight"
    assert t.departure.name == "JFK"


def test_ingest_activities(tmp_path):
    wb_path = tmp_path / "trip.xlsx"
    _create_test_workbook(wb_path)
    result = ingest_excel(wb_path)
    assert len(result["activities"]) == 1
    act = result["activities"][0]
    assert act["name"] == "Seine River Cruise"


def test_ingest_expenses(tmp_path):
    wb_path = tmp_path / "trip.xlsx"
    _create_test_workbook(wb_path)
    result = ingest_excel(wb_path)
    assert len(result["expenses"]) == 1
    exp = result["expenses"][0]
    assert exp.amount == 87.50
    assert exp.currency == "EUR"


def test_ingest_missing_tab(tmp_path):
    """Workbook missing a tab should not crash, just return empty list."""
    wb_path = tmp_path / "minimal.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Accommodations"
    ws.append(["Name", "Address", "City", "Country", "Check-In", "Check-Out"])
    wb.save(wb_path)
    result = ingest_excel(wb_path)
    assert result["transits"] == []
    assert result["expenses"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_excel.py -v`
Expected: FAIL — cannot import `excel`

- [ ] **Step 3: Implement Excel ingest**

```python
# src/post_trip_summary/pipeline/ingest/excel.py
"""Parse trip itinerary from Excel workbook."""
from datetime import date, datetime
from pathlib import Path

import openpyxl

from post_trip_summary.models import (
    Accommodation, Transit, TransitPoint, Location, Expense,
)


def _parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip())
        except ValueError:
            pass
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    return None


def _rows_as_dicts(ws) -> list[dict]:
    """Read worksheet rows as list of dicts using first row as headers."""
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return []
    headers = [str(h).strip().lower().replace(" ", "_").replace("-", "_") for h in rows[0]]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append(dict(zip(headers, row)))
    return result


def _parse_accommodations(ws) -> list[Accommodation]:
    accommodations = []
    for row in _rows_as_dicts(ws):
        check_in = _parse_date(row.get("check_in"))
        check_out = _parse_date(row.get("check_out"))
        if not check_in or not check_out:
            continue
        loc = Location(
            lat=0.0, lon=0.0,
            name=str(row.get("name", "")),
            address=row.get("address"),
            city=str(row.get("city", "")),
            country=str(row.get("country", "")),
        )
        accommodations.append(Accommodation(
            name=str(row.get("name", "")),
            location=loc,
            check_in=check_in,
            check_out=check_out,
            sources=["itinerary"],
        ))
    return accommodations


def _parse_transits(ws) -> list[Transit]:
    transits = []
    for row in _rows_as_dicts(ws):
        dep_time = _parse_datetime(row.get("departure"))
        arr_time = _parse_datetime(row.get("arrival"))
        if not dep_time or not arr_time:
            continue
        dep_loc = Location(lat=0.0, lon=0.0, name=str(row.get("from", "")), address=None, city="", country="")
        arr_loc = Location(lat=0.0, lon=0.0, name=str(row.get("to", "")), address=None, city="", country="")
        transits.append(Transit(
            mode=str(row.get("mode", "unknown")).lower(),
            departure=TransitPoint(location=dep_loc, time=dep_time, name=str(row.get("from", ""))),
            arrival=TransitPoint(location=arr_loc, time=arr_time, name=str(row.get("to", ""))),
            details={"info": row.get("details", "")},
            sources=["itinerary"],
        ))
    return transits


def _parse_activities(ws) -> list[dict]:
    """Parse activities as plain dicts — they become Events during skeleton building."""
    activities = []
    for row in _rows_as_dicts(ws):
        act_date = _parse_date(row.get("date"))
        if not act_date:
            continue
        activities.append({
            "name": str(row.get("name", "")),
            "location": str(row.get("location", "")),
            "city": str(row.get("city", "")),
            "country": str(row.get("country", "")),
            "date": act_date.isoformat(),
            "time": str(row.get("time", "")),
            "notes": str(row.get("notes", "")),
        })
    return activities


def _parse_expenses(ws) -> list[Expense]:
    expenses = []
    for row in _rows_as_dicts(ws):
        exp_date = _parse_date(row.get("date"))
        if not exp_date:
            continue
        expenses.append(Expense(
            date=exp_date,
            amount=float(row.get("amount", 0)),
            currency=str(row.get("currency", "USD")),
            merchant=str(row.get("merchant", "")),
            category=row.get("category"),
            source="spreadsheet",
        ))
    return expenses


def ingest_excel(path: Path) -> dict:
    """Parse Excel workbook and return structured trip data."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet_names_lower = {s.lower(): s for s in wb.sheetnames}

    result = {
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
    }

    if "accommodations" in sheet_names_lower:
        result["accommodations"] = _parse_accommodations(wb[sheet_names_lower["accommodations"]])
    if "transit" in sheet_names_lower:
        result["transits"] = _parse_transits(wb[sheet_names_lower["transit"]])
    if "activities" in sheet_names_lower:
        result["activities"] = _parse_activities(wb[sheet_names_lower["activities"]])
    if "expenses" in sheet_names_lower:
        result["expenses"] = _parse_expenses(wb[sheet_names_lower["expenses"]])

    wb.close()
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_excel.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/ingest/excel.py tests/test_ingest_excel.py
git commit -m "feat: add Excel workbook ingest (accommodations, transit, activities, expenses)"
```

---

### Task 8: Credit card CSV ingest

**Files:**
- Create: `src/post_trip_summary/pipeline/ingest/credit_card.py`
- Create: `tests/test_ingest_credit_card.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingest_credit_card.py
from datetime import date
from pathlib import Path
from post_trip_summary.pipeline.ingest.credit_card import ingest_credit_card


def _write_csv(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_basic_csv(tmp_path):
    csv_path = tmp_path / "transactions.csv"
    _write_csv(csv_path, """Date,Amount,Merchant,Category
2026-03-05,87.50,REST LE PETIT,Dining
2026-03-05,55.00,TAXI PARIS,Transport
2026-03-06,12.00,CAFE DES ARTS,Dining
""")
    expenses = ingest_credit_card(csv_path)
    assert len(expenses) == 3
    assert expenses[0].merchant == "REST LE PETIT"
    assert expenses[0].amount == 87.50
    assert expenses[0].date == date(2026, 3, 5)
    assert expenses[0].source == "credit_card"


def test_csv_with_currency(tmp_path):
    csv_path = tmp_path / "transactions.csv"
    _write_csv(csv_path, """Date,Amount,Currency,Merchant
2026-03-05,87.50,EUR,REST LE PETIT
""")
    expenses = ingest_credit_card(csv_path)
    assert expenses[0].currency == "EUR"


def test_csv_with_different_date_formats(tmp_path):
    csv_path = tmp_path / "transactions.csv"
    _write_csv(csv_path, """Date,Amount,Merchant
03/05/2026,10.00,SHOP A
""")
    expenses = ingest_credit_card(csv_path)
    assert len(expenses) == 1
    assert expenses[0].date == date(2026, 3, 5)


def test_empty_csv(tmp_path):
    csv_path = tmp_path / "empty.csv"
    _write_csv(csv_path, """Date,Amount,Merchant
""")
    expenses = ingest_credit_card(csv_path)
    assert expenses == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_credit_card.py -v`
Expected: FAIL

- [ ] **Step 3: Implement credit card ingest**

```python
# src/post_trip_summary/pipeline/ingest/credit_card.py
"""Parse credit card transaction CSV exports."""
import csv
from datetime import date, datetime
from pathlib import Path

from post_trip_summary.models import Expense

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%Y/%m/%d",
]


def _parse_date(value: str) -> date | None:
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_headers(headers: list[str]) -> dict[str, int]:
    """Map normalized header names to column indices."""
    mapping = {}
    for i, h in enumerate(headers):
        key = h.strip().lower().replace(" ", "_").replace("-", "_")
        mapping[key] = i
    return mapping


def ingest_credit_card(path: Path) -> list[Expense]:
    """Parse credit card CSV and return Expense list."""
    expenses = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            return []
        col = _normalize_headers(headers)

        date_idx = col.get("date")
        amount_idx = col.get("amount")
        merchant_idx = col.get("merchant")
        currency_idx = col.get("currency")
        category_idx = col.get("category")

        if date_idx is None or amount_idx is None:
            return []

        for row in reader:
            if not row or all(c.strip() == "" for c in row):
                continue
            exp_date = _parse_date(row[date_idx])
            if not exp_date:
                continue
            try:
                amount = float(row[amount_idx].strip().replace(",", ""))
            except (ValueError, IndexError):
                continue

            expenses.append(Expense(
                date=exp_date,
                amount=amount,
                currency=row[currency_idx].strip() if currency_idx is not None and currency_idx < len(row) else "USD",
                merchant=row[merchant_idx].strip() if merchant_idx is not None and merchant_idx < len(row) else "",
                category=row[category_idx].strip() if category_idx is not None and category_idx < len(row) else None,
                source="credit_card",
            ))

    return expenses
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_credit_card.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/ingest/credit_card.py tests/test_ingest_credit_card.py
git commit -m "feat: add credit card CSV ingest with flexible date parsing"
```

---

### Task 9: Google Maps Timeline ingest

**Note:** Google changed the Takeout export format in 2023/2024. This implementation targets the `timelineObjects` format (pre-2024). Users with newer exports may have per-month folder structures under `Semantic Location History/`. A future enhancement can detect the format version and parse both. For V1, document which format is expected.

**Files:**
- Create: `src/post_trip_summary/pipeline/ingest/google_maps.py`
- Create: `tests/test_ingest_google_maps.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingest_google_maps.py
import json
from datetime import datetime
from pathlib import Path
from post_trip_summary.pipeline.ingest.google_maps import ingest_google_maps


def _write_timeline(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_parse_place_visits(tmp_path):
    timeline_path = tmp_path / "Records.json"
    _write_timeline(timeline_path, {
        "timelineObjects": [
            {
                "placeVisit": {
                    "location": {
                        "latitudeE7": 488584000,
                        "longitudeE7": 22945000,
                        "name": "Eiffel Tower",
                        "address": "5 Av. Anatole France, Paris",
                    },
                    "duration": {
                        "startTimestamp": "2026-03-05T16:15:00.000Z",
                        "endTimestamp": "2026-03-05T18:00:00.000Z",
                    },
                }
            }
        ]
    })
    result = ingest_google_maps(timeline_path)
    assert len(result["place_visits"]) == 1
    visit = result["place_visits"][0]
    assert visit["name"] == "Eiffel Tower"
    assert abs(visit["lat"] - 48.8584) < 0.001


def test_parse_activity_segments(tmp_path):
    timeline_path = tmp_path / "Records.json"
    _write_timeline(timeline_path, {
        "timelineObjects": [
            {
                "activitySegment": {
                    "startLocation": {"latitudeE7": 488584000, "longitudeE7": 22945000},
                    "endLocation": {"latitudeE7": 488660000, "longitudeE7": 23522000},
                    "duration": {
                        "startTimestamp": "2026-03-05T18:00:00.000Z",
                        "endTimestamp": "2026-03-05T18:30:00.000Z",
                    },
                    "activityType": "IN_VEHICLE",
                }
            }
        ]
    })
    result = ingest_google_maps(timeline_path)
    assert len(result["activity_segments"]) == 1


def test_empty_timeline(tmp_path):
    timeline_path = tmp_path / "Records.json"
    _write_timeline(timeline_path, {"timelineObjects": []})
    result = ingest_google_maps(timeline_path)
    assert result["place_visits"] == []
    assert result["activity_segments"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_google_maps.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Google Maps ingest**

```python
# src/post_trip_summary/pipeline/ingest/google_maps.py
"""Parse Google Maps Timeline JSON export (from Google Takeout)."""
import json
from datetime import datetime, timezone
from pathlib import Path


def _parse_timestamp(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _e7_to_degrees(e7_value: int | float) -> float:
    return e7_value / 1e7


def ingest_google_maps(path: Path) -> dict:
    """Parse Google Takeout timeline JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    timeline_objects = data.get("timelineObjects", [])

    place_visits = []
    activity_segments = []

    for obj in timeline_objects:
        if "placeVisit" in obj:
            pv = obj["placeVisit"]
            loc = pv.get("location", {})
            duration = pv.get("duration", {})
            place_visits.append({
                "name": loc.get("name", ""),
                "address": loc.get("address", ""),
                "lat": _e7_to_degrees(loc.get("latitudeE7", 0)),
                "lon": _e7_to_degrees(loc.get("longitudeE7", 0)),
                "start": _parse_timestamp(duration.get("startTimestamp", "")),
                "end": _parse_timestamp(duration.get("endTimestamp", "")),
                "source": "google_maps",
            })
        elif "activitySegment" in obj:
            seg = obj["activitySegment"]
            start_loc = seg.get("startLocation", {})
            end_loc = seg.get("endLocation", {})
            duration = seg.get("duration", {})
            activity_segments.append({
                "start_lat": _e7_to_degrees(start_loc.get("latitudeE7", 0)),
                "start_lon": _e7_to_degrees(start_loc.get("longitudeE7", 0)),
                "end_lat": _e7_to_degrees(end_loc.get("latitudeE7", 0)),
                "end_lon": _e7_to_degrees(end_loc.get("longitudeE7", 0)),
                "start": _parse_timestamp(duration.get("startTimestamp", "")),
                "end": _parse_timestamp(duration.get("endTimestamp", "")),
                "activity_type": seg.get("activityType", "UNKNOWN"),
                "source": "google_maps",
            })

    return {"place_visits": place_visits, "activity_segments": activity_segments}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_google_maps.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/ingest/google_maps.py tests/test_ingest_google_maps.py
git commit -m "feat: add Google Maps Timeline JSON ingest"
```

---

### Task 10: Apple Health workout ingest

**Note:** Real Apple Health exports store workout route data in separate GPX files within the export zip, not inline in the XML. This implementation parses a simplified XML format for V1. When testing with real data, the parser may need to be extended to handle GPX route files. The test uses a simplified structure that validates the parsing logic.

**Files:**
- Create: `src/post_trip_summary/pipeline/ingest/apple_health.py`
- Create: `tests/test_ingest_apple_health.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingest_apple_health.py
from datetime import datetime
from pathlib import Path
from post_trip_summary.pipeline.ingest.apple_health import ingest_apple_health


def _write_health_xml(path: Path) -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
 <Workout workoutActivityType="HKWorkoutActivityTypeWalking"
          duration="45.5"
          durationUnit="min"
          totalDistance="3.2"
          totalDistanceUnit="km"
          startDate="2026-03-05 16:00:00 +0000"
          endDate="2026-03-05 16:45:30 +0000">
  <WorkoutRoute>
   <Location date="2026-03-05 16:00:00 +0000" latitude="48.8584" longitude="2.2945" altitude="35.0"/>
   <Location date="2026-03-05 16:15:00 +0000" latitude="48.8600" longitude="2.2960" altitude="36.0"/>
   <Location date="2026-03-05 16:30:00 +0000" latitude="48.8620" longitude="2.2980" altitude="37.0"/>
  </WorkoutRoute>
 </Workout>
</HealthData>"""
    path.write_text(xml, encoding="utf-8")


def test_parse_workout(tmp_path):
    xml_path = tmp_path / "export.xml"
    _write_health_xml(xml_path)
    result = ingest_apple_health(xml_path)
    assert len(result) == 1
    workout = result[0]
    assert workout["activity_type"] == "walking"
    assert workout["duration_minutes"] == 45.5
    assert workout["distance_km"] == 3.2


def test_parse_workout_route(tmp_path):
    xml_path = tmp_path / "export.xml"
    _write_health_xml(xml_path)
    result = ingest_apple_health(xml_path)
    workout = result[0]
    assert len(workout["route"]) == 3
    assert abs(workout["route"][0]["lat"] - 48.8584) < 0.001


def test_empty_health_data(tmp_path):
    xml_path = tmp_path / "empty.xml"
    xml_path.write_text('<?xml version="1.0"?><HealthData></HealthData>', encoding="utf-8")
    result = ingest_apple_health(xml_path)
    assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_apple_health.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Apple Health ingest**

```python
# src/post_trip_summary/pipeline/ingest/apple_health.py
"""Parse Apple Health XML export for workout routes."""
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

_ACTIVITY_MAP = {
    "HKWorkoutActivityTypeWalking": "walking",
    "HKWorkoutActivityTypeRunning": "running",
    "HKWorkoutActivityTypeHiking": "hiking",
    "HKWorkoutActivityTypeCycling": "cycling",
}

_DATE_FMT = "%Y-%m-%d %H:%M:%S %z"


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, _DATE_FMT).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def ingest_apple_health(path: Path) -> list[dict]:
    """Parse Apple Health export XML for workouts with routes."""
    tree = ET.parse(path)
    root = tree.getroot()

    workouts = []
    for workout_elem in root.iter("Workout"):
        activity_raw = workout_elem.get("workoutActivityType", "")
        activity = _ACTIVITY_MAP.get(activity_raw, activity_raw.replace("HKWorkoutActivityType", "").lower())

        start = _parse_date(workout_elem.get("startDate", ""))
        end = _parse_date(workout_elem.get("endDate", ""))

        try:
            duration = float(workout_elem.get("duration", 0))
        except (ValueError, TypeError):
            duration = 0.0

        try:
            distance = float(workout_elem.get("totalDistance", 0))
        except (ValueError, TypeError):
            distance = 0.0

        route = []
        for route_elem in workout_elem.iter("WorkoutRoute"):
            for loc_elem in route_elem.iter("Location"):
                try:
                    route.append({
                        "lat": float(loc_elem.get("latitude", 0)),
                        "lon": float(loc_elem.get("longitude", 0)),
                        "altitude": float(loc_elem.get("altitude", 0)),
                        "timestamp": _parse_date(loc_elem.get("date", "")),
                    })
                except (ValueError, TypeError):
                    continue

        workouts.append({
            "activity_type": activity,
            "start": start,
            "end": end,
            "duration_minutes": duration,
            "distance_km": distance,
            "route": route,
            "source": "apple_health",
        })

    return workouts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_apple_health.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/ingest/apple_health.py tests/test_ingest_apple_health.py
git commit -m "feat: add Apple Health XML ingest for workout routes"
```

---

### Task 11: Day One journal ingest

**Files:**
- Create: `src/post_trip_summary/pipeline/ingest/dayone.py`
- Create: `tests/test_ingest_dayone.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_ingest_dayone.py
import json
from datetime import datetime
from pathlib import Path
from post_trip_summary.pipeline.ingest.dayone import ingest_dayone


def _write_dayone_export(path: Path) -> None:
    data = {
        "entries": [
            {
                "creationDate": "2026-03-05T18:30:00Z",
                "text": "Visited the Eiffel Tower today. Amazing views!",
                "location": {
                    "latitude": 48.8584,
                    "longitude": 2.2945,
                    "placeName": "Eiffel Tower",
                },
                "photos": [
                    {"identifier": "abc123", "md5": "def456", "type": "jpeg"}
                ],
            },
            {
                "creationDate": "2026-03-06T12:00:00Z",
                "text": "Lunch at a great bistro near the Seine.",
            },
        ]
    }
    path.write_text(json.dumps(data), encoding="utf-8")


def test_parse_entries(tmp_path):
    export_path = tmp_path / "dayone.json"
    _write_dayone_export(export_path)
    result = ingest_dayone(export_path)
    assert len(result) == 2


def test_entry_with_location(tmp_path):
    export_path = tmp_path / "dayone.json"
    _write_dayone_export(export_path)
    result = ingest_dayone(export_path)
    entry = result[0]
    assert entry["text"] == "Visited the Eiffel Tower today. Amazing views!"
    assert abs(entry["lat"] - 48.8584) < 0.001
    assert entry["place_name"] == "Eiffel Tower"


def test_entry_without_location(tmp_path):
    export_path = tmp_path / "dayone.json"
    _write_dayone_export(export_path)
    result = ingest_dayone(export_path)
    entry = result[1]
    assert entry["lat"] is None
    assert entry["lon"] is None


def test_entry_photos(tmp_path):
    export_path = tmp_path / "dayone.json"
    _write_dayone_export(export_path)
    result = ingest_dayone(export_path)
    assert len(result[0]["photo_ids"]) == 1
    assert result[1]["photo_ids"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_dayone.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Day One ingest**

```python
# src/post_trip_summary/pipeline/ingest/dayone.py
"""Parse Day One journal JSON export."""
import json
from datetime import datetime
from pathlib import Path


def _parse_timestamp(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def ingest_dayone(path: Path) -> list[dict]:
    """Parse Day One JSON export and return journal entries."""
    data = json.loads(path.read_text(encoding="utf-8"))
    entries_raw = data.get("entries", [])

    entries = []
    for entry in entries_raw:
        location = entry.get("location", {})
        photos = entry.get("photos", [])

        entries.append({
            "timestamp": _parse_timestamp(entry.get("creationDate", "")),
            "text": entry.get("text", ""),
            "lat": location.get("latitude") if location else None,
            "lon": location.get("longitude") if location else None,
            "place_name": location.get("placeName", "") if location else "",
            "photo_ids": [p.get("identifier", "") for p in photos],
            "source": "dayone",
        })

    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_ingest_dayone.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/ingest/dayone.py tests/test_ingest_dayone.py
git commit -m "feat: add Day One journal JSON ingest"
```

---

## Chunk 3: Stage 2 — Skeleton Building (Clustering, Geocoding, Cross-Referencing)

### Task 12: GPS clustering

**Files:**
- Create: `src/post_trip_summary/geo/__init__.py`
- Create: `src/post_trip_summary/geo/clustering.py`
- Create: `tests/test_clustering.py`

- [ ] **Step 1: Create geo package init**

```python
# src/post_trip_summary/geo/__init__.py
```

- [ ] **Step 2: Write failing test for time-based clustering**

```python
# tests/test_clustering.py
from datetime import datetime
from pathlib import Path
from post_trip_summary.models import Photo
from post_trip_summary.geo.clustering import cluster_photos_by_time, cluster_by_gps, build_clusters


def _photo(ts: str, lat: float = 48.858, lon: float = 2.294) -> Photo:
    """Helper to create a Photo with timestamp and GPS."""
    return Photo(
        path=Path(f"/photos/{ts.replace(' ', '_').replace(':', '')}.jpg"),
        timestamp=datetime.fromisoformat(ts),
        gps=(lat, lon),
    )


def _photo_no_gps(ts: str) -> Photo:
    return Photo(path=Path(f"/photos/{ts.replace(' ', '_')}.jpg"), timestamp=datetime.fromisoformat(ts), gps=None)


def test_time_clustering_single_group():
    photos = [
        _photo("2026-03-05 16:00:00"),
        _photo("2026-03-05 16:05:00"),
        _photo("2026-03-05 16:10:00"),
    ]
    groups = cluster_photos_by_time(photos, gap_minutes=15)
    assert len(groups) == 1
    assert len(groups[0]) == 3


def test_time_clustering_two_groups():
    photos = [
        _photo("2026-03-05 16:00:00"),
        _photo("2026-03-05 16:05:00"),
        _photo("2026-03-05 17:00:00"),  # 55 min gap
        _photo("2026-03-05 17:05:00"),
    ]
    groups = cluster_photos_by_time(photos, gap_minutes=15)
    assert len(groups) == 2
    assert len(groups[0]) == 2
    assert len(groups[1]) == 2


def test_gps_subclustering():
    """Photos at same time but different locations should split."""
    photos = [
        _photo("2026-03-05 16:00:00", lat=48.858, lon=2.294),   # Eiffel Tower
        _photo("2026-03-05 16:05:00", lat=48.858, lon=2.295),   # Nearby
        _photo("2026-03-05 16:10:00", lat=48.886, lon=2.343),   # Sacre Coeur (~5km away)
    ]
    subclusters = cluster_by_gps(photos, distance_meters=200)
    assert len(subclusters) == 2


def test_build_clusters_full_pipeline():
    photos = [
        _photo("2026-03-05 10:00:00", lat=48.858, lon=2.294),
        _photo("2026-03-05 10:05:00", lat=48.858, lon=2.295),
        _photo("2026-03-05 12:00:00", lat=48.860, lon=2.336),  # Different time and place
        _photo("2026-03-05 12:10:00", lat=48.861, lon=2.337),
    ]
    clusters = build_clusters(photos, gap_minutes=15, distance_meters=200)
    assert len(clusters) == 2
    for cluster in clusters:
        assert "photos" in cluster
        assert "centroid" in cluster
        assert "time_range" in cluster


def test_cluster_centroid():
    photos = [
        _photo("2026-03-05 16:00:00", lat=48.0, lon=2.0),
        _photo("2026-03-05 16:05:00", lat=49.0, lon=3.0),
    ]
    clusters = build_clusters(photos, gap_minutes=15, distance_meters=50000)
    assert len(clusters) == 1
    centroid = clusters[0]["centroid"]
    assert abs(centroid[0] - 48.5) < 0.01
    assert abs(centroid[1] - 2.5) < 0.01


def test_photos_without_gps():
    """Photos without GPS should stay in their time cluster."""
    photos = [
        _photo_no_gps("2026-03-05 16:00:00"),
        _photo_no_gps("2026-03-05 16:05:00"),
    ]
    clusters = build_clusters(photos, gap_minutes=15, distance_meters=200)
    assert len(clusters) == 1
    assert clusters[0]["centroid"] is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_clustering.py -v`
Expected: FAIL

- [ ] **Step 4: Implement clustering**

```python
# src/post_trip_summary/geo/clustering.py
"""Photo clustering by time proximity and GPS proximity."""
from datetime import datetime, timedelta
from geopy.distance import geodesic

from post_trip_summary.models import Photo


def cluster_photos_by_time(photos: list[Photo], gap_minutes: int = 15) -> list[list[Photo]]:
    """Split sorted photos into groups where consecutive gaps exceed threshold."""
    if not photos:
        return []
    sorted_photos = sorted(photos, key=lambda p: p.timestamp)
    groups = [[sorted_photos[0]]]
    for photo in sorted_photos[1:]:
        if photo.timestamp - groups[-1][-1].timestamp > timedelta(minutes=gap_minutes):
            groups.append([])
        groups[-1].append(photo)
    return groups


def cluster_by_gps(photos: list[Photo], distance_meters: int = 200) -> list[list[Photo]]:
    """Sub-cluster a list of photos by GPS proximity using simple sequential grouping."""
    gps_photos = [p for p in photos if p.gps is not None]
    no_gps_photos = [p for p in photos if p.gps is None]

    if not gps_photos:
        return [photos] if photos else []

    clusters: list[list[Photo]] = [[gps_photos[0]]]
    for photo in gps_photos[1:]:
        merged = False
        for cluster in clusters:
            centroid = _centroid([p for p in cluster if p.gps])
            if centroid and geodesic(centroid, photo.gps).meters <= distance_meters:
                cluster.append(photo)
                merged = True
                break
        if not merged:
            clusters.append([photo])

    # Attach no-GPS photos to the first cluster
    if no_gps_photos and clusters:
        clusters[0].extend(no_gps_photos)

    return clusters


def _centroid(photos: list[Photo]) -> tuple[float, float] | None:
    """Average GPS position of photos that have GPS data."""
    gps_points = [p.gps for p in photos if p.gps is not None]
    if not gps_points:
        return None
    avg_lat = sum(g[0] for g in gps_points) / len(gps_points)
    avg_lon = sum(g[1] for g in gps_points) / len(gps_points)
    return (avg_lat, avg_lon)


def build_clusters(
    photos: list[Photo],
    gap_minutes: int = 15,
    distance_meters: int = 200,
) -> list[dict]:
    """Full clustering pipeline: time split → GPS sub-split → build cluster dicts."""
    time_groups = cluster_photos_by_time(photos, gap_minutes)
    clusters = []

    for group in time_groups:
        subclusters = cluster_by_gps(group, distance_meters)
        for subcluster in subclusters:
            sorted_sub = sorted(subcluster, key=lambda p: p.timestamp)
            centroid = _centroid(sorted_sub)
            clusters.append({
                "photos": sorted_sub,
                "centroid": centroid,
                "time_range": (sorted_sub[0].timestamp, sorted_sub[-1].timestamp),
            })

    return sorted(clusters, key=lambda c: c["time_range"][0])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_clustering.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/post_trip_summary/geo/__init__.py src/post_trip_summary/geo/clustering.py tests/test_clustering.py
git commit -m "feat: add photo clustering by time and GPS proximity"
```

---

### Task 13: Reverse geocoding

**Files:**
- Create: `src/post_trip_summary/geo/reverse_geocode.py`
- Create: `tests/test_reverse_geocode.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_reverse_geocode.py
from post_trip_summary.geo.reverse_geocode import reverse_geocode, reverse_geocode_batch


def test_reverse_geocode_paris():
    result = reverse_geocode(48.8584, 2.2945)
    assert result is not None
    assert result["country"] == "France"
    # reverse_geocoder gives nearest city — may not be exactly "Paris" but should be close
    assert len(result["city"]) > 0


def test_reverse_geocode_batch_multiple():
    coords = [
        (48.8584, 2.2945),   # Paris
        (40.7128, -74.0060),  # New York
    ]
    results = reverse_geocode_batch(coords)
    assert len(results) == 2
    countries = {r["country"] for r in results}
    assert "France" in countries or "FR" in countries


def test_reverse_geocode_invalid():
    result = reverse_geocode(0.0, 0.0)
    # Should still return something (nearest land point) without crashing
    assert result is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_reverse_geocode.py -v`
Expected: FAIL

- [ ] **Step 3: Implement reverse geocoding**

```python
# src/post_trip_summary/geo/reverse_geocode.py
"""Offline reverse geocoding using reverse_geocoder library."""
import reverse_geocoder as rg


def reverse_geocode(lat: float, lon: float) -> dict:
    """Reverse geocode a single coordinate. Returns dict with city, country, etc."""
    results = rg.search([(lat, lon)])
    if not results:
        return {"city": "", "country": "", "admin1": "", "admin2": ""}
    r = results[0]
    return {
        "city": r.get("name", ""),
        "country": r.get("cc", ""),
        "admin1": r.get("admin1", ""),
        "admin2": r.get("admin2", ""),
    }


def reverse_geocode_batch(coords: list[tuple[float, float]]) -> list[dict]:
    """Reverse geocode multiple coordinates at once (more efficient)."""
    if not coords:
        return []
    results = rg.search(coords)
    return [
        {
            "city": r.get("name", ""),
            "country": r.get("cc", ""),
            "admin1": r.get("admin1", ""),
            "admin2": r.get("admin2", ""),
        }
        for r in results
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_reverse_geocode.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/geo/reverse_geocode.py tests/test_reverse_geocode.py
git commit -m "feat: add offline reverse geocoding via reverse_geocoder"
```

---

### Task 14: Skeleton builder (cross-referencing and timeline construction)

**Files:**
- Create: `src/post_trip_summary/pipeline/skeleton.py`
- Create: `tests/test_skeleton.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_skeleton.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import (
    Photo, Location, Accommodation, Transit, TransitPoint, Expense, Event, Day, Trip,
)
from post_trip_summary.pipeline.skeleton import (
    build_skeleton, _match_cluster_to_itinerary, _match_cluster_to_expense,
    _classify_event, _assign_event_ids,
)


def _photo(ts: str, lat: float, lon: float) -> Photo:
    return Photo(path=Path(f"/p/{ts}.jpg"), timestamp=datetime.fromisoformat(ts), gps=(lat, lon))


def _make_cluster(ts_start: str, ts_end: str, lat: float, lon: float, count: int = 5) -> dict:
    return {
        "photos": [_photo(ts_start, lat, lon)] * count,
        "centroid": (lat, lon),
        "time_range": (datetime.fromisoformat(ts_start), datetime.fromisoformat(ts_end)),
    }


def test_match_cluster_to_accommodation():
    cluster = _make_cluster("2026-03-05 15:30:00", "2026-03-05 16:00:00", 48.857, 2.362)
    acc = Accommodation(
        name="Hotel Le Marais",
        location=Location(lat=48.857, lon=2.362, name="Hotel Le Marais", address="123 Rue", city="Paris", country="France"),
        check_in=date(2026, 3, 5),
        check_out=date(2026, 3, 8),
        sources=["itinerary"],
    )
    match = _match_cluster_to_itinerary(cluster, [acc], [])
    assert match is not None
    assert match["name"] == "Hotel Le Marais"
    assert match["type"] == "hotel"


def test_match_cluster_to_expense():
    cluster = _make_cluster("2026-03-05 19:00:00", "2026-03-05 19:30:00", 48.858, 2.294)
    expenses = [
        Expense(date=date(2026, 3, 5), amount=87.5, currency="EUR", merchant="REST LE PETIT", category="dining", source="credit_card"),
    ]
    match = _match_cluster_to_expense(cluster, expenses)
    assert match is not None
    assert match.merchant == "REST LE PETIT"


def test_classify_event_restaurant():
    assert _classify_event(expense_category="dining") == "restaurant"


def test_classify_event_unknown():
    assert _classify_event() == "unknown"


def test_assign_event_ids():
    events = [
        Event(id="", type="landmark", name="A", time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 11, 0)),
              location=Location(lat=0, lon=0, name="", address=None, city="", country="")),
        Event(id="", type="restaurant", name="B", time_range=(datetime(2026, 3, 5, 12, 0), datetime(2026, 3, 5, 13, 0)),
              location=Location(lat=0, lon=0, name="", address=None, city="", country="")),
    ]
    days = [Day(date=date(2026, 3, 5), events=events)]
    _assign_event_ids(days)
    assert days[0].events[0].id == "day01-event01"
    assert days[0].events[1].id == "day01-event02"


def test_build_skeleton_basic():
    photos = [
        _photo("2026-03-05 10:00:00", 48.858, 2.294),
        _photo("2026-03-05 10:05:00", 48.858, 2.295),
    ]
    trip_data = {
        "photos": photos,
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    trip = build_skeleton(trip_data, gap_minutes=15, distance_meters=200)
    assert isinstance(trip, Trip)
    assert len(trip.days) >= 1
    assert len(trip.days[0].events) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_skeleton.py -v`
Expected: FAIL

- [ ] **Step 3: Implement skeleton builder**

```python
# src/post_trip_summary/pipeline/skeleton.py
"""Build trip skeleton from clustered photos and supplementary data."""
from datetime import date, datetime, timedelta
from collections import defaultdict

from geopy.distance import geodesic

from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Accommodation, Transit, Expense,
)
from post_trip_summary.geo.clustering import build_clusters
from post_trip_summary.geo.reverse_geocode import reverse_geocode


def _match_cluster_to_itinerary(
    cluster: dict,
    accommodations: list[Accommodation],
    activities: list[dict],
) -> dict | None:
    """Check if cluster matches a known itinerary item by location and date."""
    centroid = cluster["centroid"]
    if not centroid:
        return None
    cluster_date = cluster["time_range"][0].date()

    # Check accommodations
    for acc in accommodations:
        if acc.location.lat == 0.0 and acc.location.lon == 0.0:
            continue
        if acc.check_in <= cluster_date <= acc.check_out:
            dist = geodesic(centroid, (acc.location.lat, acc.location.lon)).meters
            if dist < 500:
                return {"name": acc.name, "type": "hotel", "source": "itinerary", "location": acc.location}

    # Check activities
    for act in activities:
        act_date = date.fromisoformat(act["date"]) if isinstance(act["date"], str) else act["date"]
        if act_date == cluster_date:
            return {"name": act["name"], "type": "activity", "source": "itinerary"}

    return None


def _match_cluster_to_expense(cluster: dict, expenses: list[Expense]) -> Expense | None:
    """Find an expense on the same date as the cluster."""
    cluster_date = cluster["time_range"][0].date()
    for exp in expenses:
        if exp.date == cluster_date and exp.event_id is None:
            return exp
    return None


def _match_cluster_to_google_maps(cluster: dict, place_visits: list[dict]) -> dict | None:
    """Match cluster to a Google Maps place visit by time and location proximity."""
    centroid = cluster["centroid"]
    c_start, c_end = cluster["time_range"]
    for visit in place_visits:
        v_start = visit.get("start")
        v_end = visit.get("end")
        if not v_start or not v_end:
            continue
        # Check time overlap
        if c_start <= v_end and c_end >= v_start:
            if centroid and visit.get("lat") and visit.get("lon"):
                dist = geodesic(centroid, (visit["lat"], visit["lon"])).meters
                if dist < 500:
                    return visit
    return None


def _classify_event(
    itinerary_match: dict | None = None,
    expense_category: str | None = None,
    google_match: dict | None = None,
) -> str:
    """Determine event type from available signals."""
    if itinerary_match:
        return itinerary_match.get("type", "unknown")
    if expense_category:
        category_map = {"dining": "restaurant", "transport": "transit", "activity": "activity", "shopping": "landmark"}
        return category_map.get(expense_category.lower(), "unknown")
    return "unknown"


def _assign_event_ids(days: list[Day]) -> None:
    """Assign unique IDs to all events."""
    for day_idx, day in enumerate(days):
        for event_idx, event in enumerate(day.events):
            event.id = f"day{day_idx + 1:02d}-event{event_idx + 1:02d}"


def build_skeleton(
    trip_data: dict,
    gap_minutes: int = 15,
    distance_meters: int = 200,
) -> Trip:
    """Build a Trip skeleton from ingested data."""
    photos: list[Photo] = trip_data.get("photos", [])
    accommodations: list[Accommodation] = trip_data.get("accommodations", [])
    transits: list[Transit] = trip_data.get("transits", [])
    activities: list[dict] = trip_data.get("activities", [])
    expenses: list[Expense] = trip_data.get("expenses", [])
    google_maps = trip_data.get("google_maps", {})
    place_visits = google_maps.get("place_visits", [])
    health_workouts = trip_data.get("apple_health", [])
    dayone_entries = trip_data.get("dayone", [])

    # Cluster photos
    clusters = build_clusters(photos, gap_minutes, distance_meters)

    # Determine date range
    all_dates = set()
    for c in clusters:
        all_dates.add(c["time_range"][0].date())
        all_dates.add(c["time_range"][1].date())
    for acc in accommodations:
        d = acc.check_in
        while d <= acc.check_out:
            all_dates.add(d)
            d += timedelta(days=1)

    if not all_dates:
        return Trip(name="", date_range=(date.today(), date.today()))

    date_range = (min(all_dates), max(all_dates))

    # Build events from clusters
    events_by_date: dict[date, list[Event]] = defaultdict(list)

    for cluster in clusters:
        c_date = cluster["time_range"][0].date()
        centroid = cluster["centroid"]

        # Cross-reference
        itinerary_match = _match_cluster_to_itinerary(cluster, accommodations, activities)
        expense_match = _match_cluster_to_expense(cluster, expenses)
        google_match = _match_cluster_to_google_maps(cluster, place_visits)

        # Determine name and type
        sources = ["exif"]

        # Check Apple Health workouts for time overlap
        for workout in health_workouts:
            w_start = workout.get("start")
            w_end = workout.get("end")
            if w_start and w_end and cluster["time_range"][0] <= w_end and cluster["time_range"][1] >= w_start:
                sources.append("apple_health")
                break

        # Check Day One entries for time overlap
        dayone_name = ""
        for entry in dayone_entries:
            e_ts = entry.get("timestamp")
            if e_ts and cluster["time_range"][0] <= e_ts <= cluster["time_range"][1]:
                sources.append("dayone")
                dayone_name = entry.get("place_name", "")
                break
        event_type = "unknown"
        name = ""

        if google_match:
            name = google_match.get("name", "")
            sources.append("google_maps")
        if itinerary_match:
            name = name or itinerary_match.get("name", "")
            event_type = itinerary_match.get("type", "unknown")
            sources.append("itinerary")
        if expense_match:
            if not name:
                name = expense_match.merchant
            if event_type == "unknown":
                event_type = _classify_event(expense_category=expense_match.category)
            sources.append("credit_card")

        if event_type == "unknown":
            event_type = _classify_event(itinerary_match, expense_match.category if expense_match else None, google_match)

        # Build location
        if centroid:
            geo = reverse_geocode(centroid[0], centroid[1])
            location = Location(
                lat=centroid[0], lon=centroid[1],
                name=name or geo.get("city", ""),
                address=None,
                city=geo.get("city", ""),
                country=geo.get("country", ""),
            )
        else:
            location = Location(lat=0, lon=0, name=name, address=None, city="", country="")

        event = Event(
            id="",
            type=event_type,
            name=name or location.city or "Unknown",
            time_range=cluster["time_range"],
            location=location,
            photos=cluster["photos"],
            description="",
            notes="",
            sources=sources,
        )
        events_by_date[c_date].append(event)

    # Add transit events
    for transit in transits:
        t_date = transit.departure.time.date()
        transit_event = Event(
            id="",
            type="transit",
            name=f"{transit.mode.title()}: {transit.departure.name} → {transit.arrival.name}",
            time_range=(transit.departure.time, transit.arrival.time),
            location=transit.departure.location,
            photos=[],
            description=str(transit.details.get("info", "")),
            notes="",
            sources=transit.sources,
        )
        events_by_date[t_date].append(transit_event)

    # Build days
    days = []
    current = date_range[0]
    while current <= date_range[1]:
        day_events = sorted(events_by_date.get(current, []), key=lambda e: e.time_range[0])
        days.append(Day(date=current, events=day_events))
        current += timedelta(days=1)

    _assign_event_ids(days)

    return Trip(
        name="",
        date_range=date_range,
        days=days,
        accommodations=accommodations,
        transits=transits,
        expenses=expenses,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_skeleton.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/skeleton.py tests/test_skeleton.py
git commit -m "feat: add skeleton builder with clustering, cross-referencing, and timeline construction"
```

---

## Chunk 4: Stages 3 & 5 — Interactive Review

### Task 15: Skeleton review (Stage 3)

**Files:**
- Create: `src/post_trip_summary/pipeline/review_skeleton.py`
- Create: `tests/test_review_skeleton.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_review_skeleton.py
from datetime import date, datetime
from post_trip_summary.models import Trip, Day, Event, Location
from post_trip_summary.pipeline.review_skeleton import format_day_summary, format_event_line


def _event(id: str, type: str, name: str, start: str, end: str) -> Event:
    return Event(
        id=id, type=type, name=name,
        time_range=(datetime.fromisoformat(start), datetime.fromisoformat(end)),
        location=Location(lat=0, lon=0, name=name, address=None, city="Paris", country="France"),
        photos=[],
        description="",
        notes="",
        sources=["exif"],
    )


def test_format_event_line_landmark():
    event = _event("day01-event01", "landmark", "Eiffel Tower", "2026-03-05 16:15:00", "2026-03-05 18:00:00")
    line = format_event_line(event, index=1)
    assert "Eiffel Tower" in line
    assert "4:15 PM" in line or "16:15" in line


def test_format_event_line_restaurant():
    event = _event("day01-event02", "restaurant", "REST LE PETIT", "2026-03-05 19:30:00", "2026-03-05 20:30:00")
    line = format_event_line(event, index=2)
    assert "REST LE PETIT" in line


def test_format_event_line_transit():
    event = _event("day01-event03", "transit", "Flight: JFK → CDG", "2026-03-05 08:00:00", "2026-03-05 14:00:00")
    line = format_event_line(event, index=3)
    assert "JFK" in line


def test_format_day_summary():
    events = [
        _event("day01-event01", "transit", "Flight: JFK → CDG", "2026-03-05 08:00:00", "2026-03-05 14:00:00"),
        _event("day01-event02", "hotel", "Hotel Le Marais", "2026-03-05 15:30:00", "2026-03-05 16:00:00"),
    ]
    day = Day(date=date(2026, 3, 5), events=events)
    summary = format_day_summary(day, day_num=1)
    assert "Day 1" in summary
    assert "March 5" in summary or "Mar" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_review_skeleton.py -v`
Expected: FAIL

- [ ] **Step 3: Implement skeleton review**

```python
# src/post_trip_summary/pipeline/review_skeleton.py
"""Stage 3: Interactive skeleton review in terminal."""
import click
from datetime import datetime

from post_trip_summary.models import Trip, Day, Event


_TYPE_ICONS = {
    "landmark": "📍",
    "restaurant": "🍽",
    "hotel": "🏨",
    "activity": "🎯",
    "transit": "✈",
    "unknown": "❓",
}


def _format_time(dt: datetime) -> str:
    try:
        return dt.strftime("%#I:%M %p")  # Windows
    except ValueError:
        return dt.strftime("%-I:%M %p")  # Unix


def format_event_line(event: Event, index: int) -> str:
    """Format a single event as a summary line."""
    icon = _TYPE_ICONS.get(event.type, "❓")
    start = _format_time(event.time_range[0])
    end = _format_time(event.time_range[1])
    photo_count = len(event.photos)
    sources = ", ".join(event.sources)

    line = f" {index:2d}. {icon} {event.name:<30s} {start}-{end}"
    if photo_count > 0:
        line += f"  ({photo_count} photos)"
    if sources:
        line += f"  [{sources}]"
    return line


def format_day_summary(day: Day, day_num: int) -> str:
    """Format a full day summary for display."""
    date_str = day.date.strftime("%B %d")
    header = f"── Day {day_num}: {date_str} ──────────────"
    lines = [header]
    for i, event in enumerate(day.events, 1):
        lines.append(format_event_line(event, i))
    return "\n".join(lines)


def review_skeleton(trip: Trip) -> Trip:
    """Interactive loop: present each day, let user confirm or edit."""
    click.echo("\n═══ Trip Skeleton Review ═══\n")
    click.echo(f"Trip: {trip.name}")
    click.echo(f"Dates: {trip.date_range[0]} to {trip.date_range[1]}")
    click.echo(f"Total days: {len(trip.days)}\n")

    for day_num, day in enumerate(trip.days, 1):
        if not day.events:
            continue

        click.echo(format_day_summary(day, day_num))
        click.echo()

        while True:
            choice = click.prompt(
                "Does this look right? [y]es / [e]dit / [s]kip",
                type=str, default="y",
            ).lower().strip()

            if choice in ("y", "yes"):
                break
            elif choice in ("s", "skip"):
                break
            elif choice in ("e", "edit"):
                _edit_day(day, day_num)
                click.echo(format_day_summary(day, day_num))
                click.echo()
            else:
                click.echo("Please enter y, e, or s.")

    click.echo("\n═══ Skeleton review complete ═══\n")
    return trip


def _edit_day(day: Day, day_num: int) -> None:
    """Let user edit events in a day."""
    click.echo("\nEditing options:")
    click.echo("  [r]ename <n> <new name>  — rename event n")
    click.echo("  [d]elete <n>             — remove event n")
    click.echo("  [a]dd                    — add a new event")
    click.echo("  [n]ote <n> <text>        — add note to event n")
    click.echo("  [done]                   — finish editing this day")

    while True:
        cmd = click.prompt("edit", type=str, default="done").strip()
        if cmd == "done":
            break

        parts = cmd.split(maxsplit=2)
        action = parts[0].lower() if parts else ""

        if action in ("r", "rename") and len(parts) >= 3:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(day.events):
                    day.events[idx].name = parts[2]
                    click.echo(f"  Renamed event {idx + 1} to '{parts[2]}'")
                else:
                    click.echo(f"  Invalid event number: {parts[1]}")
            except ValueError:
                click.echo("  Usage: rename <number> <new name>")

        elif action in ("d", "delete") and len(parts) >= 2:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(day.events):
                    removed = day.events.pop(idx)
                    click.echo(f"  Removed: {removed.name}")
                else:
                    click.echo(f"  Invalid event number: {parts[1]}")
            except ValueError:
                click.echo("  Usage: delete <number>")

        elif action in ("n", "note") and len(parts) >= 3:
            try:
                idx = int(parts[1]) - 1
                if 0 <= idx < len(day.events):
                    day.events[idx].notes = parts[2]
                    click.echo(f"  Added note to event {idx + 1}")
                else:
                    click.echo(f"  Invalid event number: {parts[1]}")
            except ValueError:
                click.echo("  Usage: note <number> <text>")

        elif action in ("a", "add"):
            name = click.prompt("  Event name")
            event_type = click.prompt("  Type (landmark/restaurant/hotel/activity/transit/unknown)", default="unknown")
            from post_trip_summary.models import Location
            new_event = Event(
                id=f"day{day_num:02d}-event{len(day.events) + 1:02d}",
                type=event_type, name=name,
                time_range=(day.events[-1].time_range[1] if day.events else
                           datetime.combine(day.date, datetime.min.time()),
                           day.events[-1].time_range[1] if day.events else
                           datetime.combine(day.date, datetime.min.time())),
                location=Location(lat=0, lon=0, name=name, address=None, city="", country=""),
                photos=[], description="", notes="", sources=["manual"],
            )
            day.events.append(new_event)
            click.echo(f"  Added: {name}")

        else:
            click.echo("  Unknown command. Enter 'done' to finish.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_review_skeleton.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/review_skeleton.py tests/test_review_skeleton.py
git commit -m "feat: add interactive skeleton review (Stage 3)"
```

---

### Task 16: Detail review (Stage 5)

**Files:**
- Create: `src/post_trip_summary/pipeline/review_details.py`
- Create: `tests/test_review_details.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_review_details.py
from datetime import datetime
from pathlib import Path
from post_trip_summary.models import Event, Photo, Location
from post_trip_summary.pipeline.review_details import format_event_detail


def _photo(name: str, highlight: bool = False, desc: str | None = None) -> Photo:
    return Photo(path=Path(f"/photos/{name}.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294), is_highlight=highlight, ai_description=desc)


def test_format_event_detail():
    event = Event(
        id="day01-event01", type="landmark", name="Eiffel Tower",
        time_range=(datetime(2026, 3, 5, 16, 15), datetime(2026, 3, 5, 18, 0)),
        location=Location(lat=48.858, lon=2.294, name="Eiffel Tower", address=None, city="Paris", country="France"),
        photos=[
            _photo("img001", highlight=True, desc="Family at Eiffel Tower"),
            _photo("img002", highlight=True, desc="Tower from Trocadéro"),
            _photo("img003", highlight=False),
        ],
        description="Visit to the Eiffel Tower",
        notes="",
        sources=["exif", "itinerary"],
    )
    output = format_event_detail(event)
    assert "Eiffel Tower" in output
    assert "Family at Eiffel Tower" in output
    assert "highlight" in output.lower() or "★" in output
    assert "3 total" in output or "3" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_review_details.py -v`
Expected: FAIL

- [ ] **Step 3: Implement detail review**

```python
# src/post_trip_summary/pipeline/review_details.py
"""Stage 5: Interactive review of enriched event details."""
import click
from pathlib import Path

from post_trip_summary.models import Trip, Event, Photo


def _format_time(dt) -> str:
    try:
        return dt.strftime("%#I:%M %p")  # Windows
    except ValueError:
        return dt.strftime("%-I:%M %p")  # Unix


def format_event_detail(event: Event) -> str:
    """Format enriched event details for terminal display."""
    start = _format_time(event.time_range[0])
    end = _format_time(event.time_range[1])
    lines = [
        f"── {event.name} ({start}-{end}) ──────────",
        f"Type: {event.type}  |  Location: {event.location.city}, {event.location.country}",
    ]
    if event.description:
        lines.append(f"Description: {event.description}")
    if event.notes:
        lines.append(f"Notes: {event.notes}")

    total = len(event.photos)
    highlights = [p for p in event.photos if p.is_highlight]
    lines.append(f"Photos: {total} total, {len(highlights)} selected as highlights")

    for i, photo in enumerate(highlights, 1):
        desc = photo.ai_description or photo.path.name
        lines.append(f"  [{i}] {desc}  ★ highlight")

    lines.append(f"Sources: {', '.join(event.sources)}")
    return "\n".join(lines)


def review_details(trip: Trip) -> Trip:
    """Interactive loop: present enriched details event by event."""
    click.echo("\n═══ Detail Review ═══\n")

    for day in trip.days:
        for event in day.events:
            if not event.photos:
                continue

            click.echo(format_event_detail(event))
            click.echo()

            while True:
                choice = click.prompt(
                    "Accept? [y]es / [e]dit description / [n]ote / [p]hotos / [s]kip",
                    type=str, default="y",
                ).lower().strip()

                if choice in ("y", "yes"):
                    break
                elif choice in ("s", "skip"):
                    break
                elif choice in ("e", "edit"):
                    new_desc = click.prompt("New description", default=event.description)
                    event.description = new_desc
                    click.echo("  Updated description.")
                elif choice in ("n", "note"):
                    note = click.prompt("Add note", default=event.notes)
                    event.notes = note
                    click.echo("  Updated notes.")
                elif choice in ("p", "photos"):
                    _edit_photo_selection(event)
                    click.echo(format_event_detail(event))
                    click.echo()
                else:
                    click.echo("Please enter y, e, n, p, or s.")

    click.echo("\n═══ Detail review complete ═══\n")
    return trip


def _edit_photo_selection(event: Event) -> None:
    """Let user toggle highlight status of photos."""
    click.echo(f"\n  All photos for '{event.name}':")
    for i, photo in enumerate(event.photos, 1):
        marker = "★" if photo.is_highlight else " "
        desc = photo.ai_description or photo.path.name
        click.echo(f"    {marker} [{i}] {desc}")

    click.echo("  Enter photo numbers to toggle (comma-separated), or 'done':")
    while True:
        inp = click.prompt("  toggle", type=str, default="done").strip()
        if inp == "done":
            break
        try:
            indices = [int(x.strip()) - 1 for x in inp.split(",")]
            for idx in indices:
                if 0 <= idx < len(event.photos):
                    event.photos[idx].is_highlight = not event.photos[idx].is_highlight
                    status = "★" if event.photos[idx].is_highlight else "removed"
                    click.echo(f"    Photo {idx + 1}: {status}")
        except ValueError:
            click.echo("    Enter numbers separated by commas, or 'done'.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_review_details.py -v`
Expected: 1 test PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/review_details.py tests/test_review_details.py
git commit -m "feat: add interactive detail review (Stage 5)"
```

---

## Chunk 5: Stage 4 — Vision & Enrichment

### Task 17: Vision API client abstraction

**Files:**
- Create: `src/post_trip_summary/vision/__init__.py`
- Create: `src/post_trip_summary/vision/client.py`
- Create: `tests/test_vision_client.py`

- [ ] **Step 1: Create vision package init**

```python
# src/post_trip_summary/vision/__init__.py
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_vision_client.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from post_trip_summary.vision.client import VisionClient, VisionResult


def test_vision_result_creation():
    result = VisionResult(description="Eiffel Tower from Trocadéro", landmark="Eiffel Tower", text_found=None, confidence="high")
    assert result.landmark == "Eiffel Tower"
    assert result.text_found is None


def test_vision_client_analyze_mock():
    """Test that analyze calls the API with correct structure."""
    with patch("post_trip_summary.vision.client.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"description": "Eiffel Tower", "landmark": "Eiffel Tower", "text_found": null}')]
        mock_client.messages.create.return_value = mock_response

        client = VisionClient(api_key="test-key")
        # Create a tiny valid JPEG for testing
        import struct
        jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 100 + b'\xff\xd9'
        result = client.analyze(image_data=jpeg_bytes, media_type="image/jpeg", purpose="landmark")
        assert mock_client.messages.create.called


def test_estimate_cost():
    client = VisionClient.__new__(VisionClient)
    cost = client.estimate_cost(num_images=100, avg_tokens_per_image=1500)
    assert cost > 0
    assert isinstance(cost, float)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_vision_client.py -v`
Expected: FAIL

- [ ] **Step 4: Implement vision client**

```python
# src/post_trip_summary/vision/client.py
"""AI vision API abstraction layer (Claude Vision)."""
import base64
import json
from dataclasses import dataclass

import anthropic


@dataclass
class VisionResult:
    description: str
    landmark: str | None = None
    text_found: str | None = None
    confidence: str = "medium"


# Approximate Claude pricing (input tokens for images)
# Claude vision: ~1600 tokens per image + output tokens
_INPUT_COST_PER_MTOK = 3.0   # $/M input tokens (Claude Sonnet)
_OUTPUT_COST_PER_MTOK = 15.0  # $/M output tokens


class VisionClient:
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def analyze(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "landmark",
    ) -> VisionResult:
        """Send an image to Claude Vision and parse the result."""
        from post_trip_summary.vision.prompts import get_prompt

        b64_image = base64.b64encode(image_data).decode("utf-8")
        prompt = get_prompt(purpose)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64_image},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        text = response.content[0].text
        try:
            data = json.loads(text)
            return VisionResult(
                description=data.get("description", ""),
                landmark=data.get("landmark"),
                text_found=data.get("text_found"),
                confidence=data.get("confidence", "medium"),
            )
        except json.JSONDecodeError:
            return VisionResult(description=text)

    def estimate_cost(self, num_images: int, avg_tokens_per_image: int = 1600) -> float:
        """Estimate API cost for a batch of images."""
        input_tokens = num_images * avg_tokens_per_image
        output_tokens = num_images * 200  # ~200 output tokens per response
        input_cost = (input_tokens / 1_000_000) * _INPUT_COST_PER_MTOK
        output_cost = (output_tokens / 1_000_000) * _OUTPUT_COST_PER_MTOK
        return round(input_cost + output_cost, 4)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_vision_client.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/post_trip_summary/vision/__init__.py src/post_trip_summary/vision/client.py tests/test_vision_client.py
git commit -m "feat: add Claude Vision API client with cost estimation"
```

---

### Task 18: Vision prompt templates

**Files:**
- Create: `src/post_trip_summary/vision/prompts.py`
- Create: `tests/test_vision_prompts.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_vision_prompts.py
from post_trip_summary.vision.prompts import get_prompt, PURPOSES


def test_all_purposes_have_prompts():
    for purpose in PURPOSES:
        prompt = get_prompt(purpose)
        assert isinstance(prompt, str)
        assert len(prompt) > 50


def test_landmark_prompt_requests_json():
    prompt = get_prompt("landmark")
    assert "JSON" in prompt or "json" in prompt


def test_sign_prompt_requests_text():
    prompt = get_prompt("sign")
    assert "text" in prompt.lower()


def test_unknown_purpose_raises():
    import pytest
    with pytest.raises(ValueError):
        get_prompt("nonexistent")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_vision_prompts.py -v`
Expected: FAIL

- [ ] **Step 3: Implement prompts**

```python
# src/post_trip_summary/vision/prompts.py
"""Prompt templates for vision API calls."""

PURPOSES = ("landmark", "sign", "scene")

_PROMPTS = {
    "landmark": """Analyze this photo and identify any landmarks or notable locations.

Respond with JSON only:
{
  "description": "Brief description of what's in the photo",
  "landmark": "Name of the landmark if identifiable, or null",
  "confidence": "high/medium/low"
}""",

    "sign": """Read any visible text in this photo — signs, menus, storefronts, plaques, street names.

Respond with JSON only:
{
  "description": "Brief description of the sign or text context",
  "text_found": "The text you can read, or null if none visible",
  "confidence": "high/medium/low"
}""",

    "scene": """Describe this vacation photo briefly for a trip journal. Focus on what's happening, who/what is visible, and the setting.

Respond with JSON only:
{
  "description": "2-3 sentence description suitable for a trip journal",
  "landmark": "Name of any recognizable landmark, or null",
  "text_found": "Any readable text in the image, or null",
  "confidence": "high/medium/low"
}""",
}


def get_prompt(purpose: str) -> str:
    """Get the prompt template for a given purpose."""
    if purpose not in _PROMPTS:
        raise ValueError(f"Unknown purpose: {purpose}. Must be one of: {PURPOSES}")
    return _PROMPTS[purpose]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_vision_prompts.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/vision/prompts.py tests/test_vision_prompts.py
git commit -m "feat: add vision prompt templates for landmark, sign, and scene analysis"
```

---

### Task 19: Photo triage and deduplication

**Files:**
- Create: `src/post_trip_summary/vision/triage.py`
- Create: `tests/test_triage.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_triage.py
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from post_trip_summary.models import Photo, Event, Location
from post_trip_summary.vision.triage import select_representatives, is_confidently_identified, estimate_batch_cost


def _photo(name: str, lat: float = 48.858, lon: float = 2.294) -> Photo:
    return Photo(path=Path(f"/photos/{name}.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(lat, lon))


def _event(name: str, sources: list[str], photos: list[Photo] | None = None) -> Event:
    return Event(
        id="day01-event01", type="landmark", name=name,
        time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
        location=Location(lat=48.858, lon=2.294, name=name, address=None, city="Paris", country="France"),
        photos=photos or [_photo(f"img{i}") for i in range(10)],
        description="", notes="", sources=sources,
    )


def test_confidently_identified_two_sources():
    event = _event("Eiffel Tower", sources=["exif", "itinerary"])
    assert is_confidently_identified(event) is True


def test_not_confidently_identified_one_source():
    event = _event("Unknown", sources=["exif"])
    assert is_confidently_identified(event) is False


def test_select_representatives_limits_count():
    photos = [_photo(f"img{i}") for i in range(50)]
    selected = select_representatives(photos, max_count=5)
    assert len(selected) <= 5


def test_select_representatives_returns_photos():
    photos = [_photo(f"img{i}") for i in range(3)]
    selected = select_representatives(photos, max_count=5)
    assert len(selected) == 3  # All 3 when under limit


def test_estimate_batch_cost():
    cost = estimate_batch_cost(num_images=100)
    assert cost > 0
    assert isinstance(cost, float)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_triage.py -v`
Expected: FAIL

- [ ] **Step 3: Implement triage**

```python
# src/post_trip_summary/vision/triage.py
"""Photo selection, deduplication, and cost estimation for vision API."""
from pathlib import Path

from post_trip_summary.models import Photo, Event
from post_trip_summary.vision.client import VisionClient


def is_confidently_identified(event: Event) -> bool:
    """An event is confident if confirmed by 2+ independent sources."""
    return len(event.sources) >= 2


def _deduplicate_by_hash(photos: list[Photo]) -> list[Photo]:
    """Remove perceptually similar photos using imagehash."""
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        return photos

    seen_hashes = set()
    unique = []
    for photo in photos:
        try:
            img = Image.open(photo.path)
            h = str(imagehash.average_hash(img))
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique.append(photo)
        except Exception:
            unique.append(photo)  # Keep photos we can't hash
    return unique


def select_representatives(photos: list[Photo], max_count: int = 5) -> list[Photo]:
    """Select representative photos from a cluster for API analysis."""
    if len(photos) <= max_count:
        return list(photos)

    # Try deduplication first
    unique = _deduplicate_by_hash(photos)
    if len(unique) <= max_count:
        return unique

    # Spread evenly across the time range
    step = len(unique) / max_count
    selected = []
    for i in range(max_count):
        idx = int(i * step)
        selected.append(unique[idx])
    return selected


def estimate_batch_cost(num_images: int) -> float:
    """Estimate cost for analyzing a batch of images."""
    client = VisionClient.__new__(VisionClient)
    return client.estimate_cost(num_images)


def plan_enrichment(events: list[Event], max_per_event: int = 5) -> list[dict]:
    """Plan which photos to send to the API for each event.

    Returns a list of dicts: {"event": Event, "photos": [Photo], "purpose": str}
    Skips confidently identified events (only sends 1 for scene description).
    """
    plan = []
    for event in events:
        if not event.photos:
            continue

        if is_confidently_identified(event):
            # Already identified — just get a scene description for 1 photo
            reps = select_representatives(event.photos, max_count=1)
            plan.append({"event": event, "photos": reps, "purpose": "scene"})
        else:
            reps = select_representatives(event.photos, max_count=max_per_event)
            plan.append({"event": event, "photos": reps, "purpose": "landmark"})

    return plan
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_triage.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/vision/triage.py tests/test_triage.py
git commit -m "feat: add photo triage with dedup, representative selection, and cost estimation"
```

---

### Task 20: Enrichment pipeline (Stage 4)

**Files:**
- Create: `src/post_trip_summary/pipeline/enrich.py`
- Create: `tests/test_enrich.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_enrich.py
from datetime import datetime, date
from pathlib import Path
from unittest.mock import patch, MagicMock
from post_trip_summary.models import Trip, Day, Event, Photo, Location
from post_trip_summary.vision.client import VisionResult
from post_trip_summary.pipeline.enrich import enrich_trip, _select_highlights


def _photo(name: str) -> Photo:
    return Photo(path=Path(f"/photos/{name}.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294))


def _event(name: str, sources: list[str], num_photos: int = 10) -> Event:
    return Event(
        id="day01-event01", type="unknown", name=name,
        time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
        location=Location(lat=48.858, lon=2.294, name=name, address=None, city="Paris", country="France"),
        photos=[_photo(f"img{i}") for i in range(num_photos)],
        description="", notes="", sources=sources,
    )


def test_select_highlights_default():
    photos = [_photo(f"img{i}") for i in range(20)]
    highlights = _select_highlights(photos, max_count=5)
    assert len(highlights) == 5
    assert all(p.is_highlight for p in highlights)


def test_select_highlights_fewer_than_max():
    photos = [_photo(f"img{i}") for i in range(3)]
    highlights = _select_highlights(photos, max_count=5)
    assert len(highlights) == 3


def test_enrich_applies_vision_results():
    """Mock the vision client and verify enrichment updates events."""
    event = _event("Unknown Place", sources=["exif"], num_photos=3)
    trip = Trip(
        name="Test", date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )

    mock_result = VisionResult(description="The Eiffel Tower", landmark="Eiffel Tower", confidence="high")

    with patch("post_trip_summary.pipeline.enrich.VisionClient") as MockClient:
        instance = MockClient.return_value
        instance.analyze.return_value = mock_result
        instance.estimate_cost.return_value = 0.01

        enriched = enrich_trip(trip, api_key="test", auto_approve=True)
        assert enriched.days[0].events[0].description == "The Eiffel Tower"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_enrich.py -v`
Expected: FAIL

- [ ] **Step 3: Implement enrichment pipeline**

```python
# src/post_trip_summary/pipeline/enrich.py
"""Stage 4: Enrich events with AI vision analysis."""
import click
from pathlib import Path

from post_trip_summary.models import Trip, Photo
from post_trip_summary.vision.client import VisionClient
from post_trip_summary.vision.triage import plan_enrichment, estimate_batch_cost


def _select_highlights(photos: list[Photo], max_count: int = 5) -> list[Photo]:
    """Mark the best photos as highlights. Returns the highlighted subset."""
    # Spread evenly across the photo set
    if len(photos) <= max_count:
        for p in photos:
            p.is_highlight = True
        return photos

    step = len(photos) / max_count
    selected = []
    for i in range(max_count):
        idx = int(i * step)
        photos[idx].is_highlight = True
        selected.append(photos[idx])
    return selected


def _read_image(path: Path) -> tuple[bytes, str]:
    """Read image file and determine media type."""
    suffix = path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".heic": "image/heic",
        ".heif": "image/heif", ".webp": "image/webp",
        ".tiff": "image/tiff", ".tif": "image/tiff",
    }
    media_type = media_types.get(suffix, "image/jpeg")
    return path.read_bytes(), media_type


def enrich_trip(trip: Trip, api_key: str | None = None, auto_approve: bool = False) -> Trip:
    """Run vision analysis on representative photos and update events."""
    # Collect all events with photos
    all_events = [event for day in trip.days for event in day.events if event.photos]

    # Plan which photos to analyze
    enrichment_plan = plan_enrichment(all_events)
    total_images = sum(len(item["photos"]) for item in enrichment_plan)

    if total_images == 0:
        click.echo("No photos need vision analysis.")
        return trip

    # Cost gate
    estimated_cost = estimate_batch_cost(total_images)
    click.echo(f"\n═══ Vision Enrichment ═══")
    click.echo(f"Photos to analyze: {total_images} across {len(enrichment_plan)} events")
    click.echo(f"Estimated cost: ${estimated_cost:.4f}")

    if not auto_approve:
        choice = click.prompt(
            "\n[a]pprove / [r]educe scope / [s]kip enrichment",
            type=str, default="a",
        ).lower().strip()

        if choice in ("s", "skip"):
            click.echo("Skipping enrichment. Selecting highlights only.")
            for event in all_events:
                _select_highlights(event.photos)
            return trip
        elif choice in ("r", "reduce"):
            click.echo("Reducing to most uncertain events only.")
            enrichment_plan = [p for p in enrichment_plan if p["purpose"] != "scene"]
            total_images = sum(len(item["photos"]) for item in enrichment_plan)
            new_cost = estimate_batch_cost(total_images)
            click.echo(f"Reduced to {total_images} images. New estimate: ${new_cost:.4f}")

    # Run analysis
    client = VisionClient(api_key=api_key)

    for item in enrichment_plan:
        event = item["event"]
        photos = item["photos"]
        purpose = item["purpose"]

        best_description = ""
        best_landmark = None

        for photo in photos:
            try:
                image_data, media_type = _read_image(photo.path)
                result = client.analyze(image_data, media_type, purpose)
                photo.ai_description = result.description
                if result.landmark and not best_landmark:
                    best_landmark = result.landmark
                if result.description and not best_description:
                    best_description = result.description
            except Exception as e:
                click.echo(f"  Warning: Failed to analyze {photo.path.name}: {e}")

        # Update event
        if best_description and not event.description:
            event.description = best_description
        if best_landmark and event.name in ("Unknown", event.location.city, ""):
            event.name = best_landmark

        # Select highlights
        _select_highlights(event.photos)

    click.echo(f"\nEnrichment complete. Analyzed {total_images} photos.")
    return trip
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_enrich.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/pipeline/enrich.py tests/test_enrich.py
git commit -m "feat: add enrichment pipeline with vision API, cost gate, and highlight selection"
```

---

## Chunk 6: Stage 6 — Output Generation, Preview, and CLI Wiring

### Task 21: Jinja2 templates

**Files:**
- Create: `src/post_trip_summary/templates/base.html`
- Create: `src/post_trip_summary/templates/detailed_record.html`
- Create: `src/post_trip_summary/templates/shareable_summary.html`
- Create: `src/post_trip_summary/templates/blog_post.html`

- [ ] **Step 1: Create base template**

```html
<!-- src/post_trip_summary/templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Trip Summary{% endblock %}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 1000px; margin: 0 auto; padding: 20px; }
        h1 { font-size: 2em; margin-bottom: 0.5em; color: #1a1a1a; }
        h2 { font-size: 1.5em; margin: 1.5em 0 0.5em; color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 0.3em; }
        h3 { font-size: 1.2em; margin: 1em 0 0.3em; color: #34495e; }
        .trip-header { text-align: center; margin-bottom: 2em; padding: 2em; background: #f8f9fa; border-radius: 8px; }
        .trip-header .dates { color: #666; font-size: 1.1em; }
        .day-section { margin: 2em 0; }
        .event { margin: 1em 0; padding: 1em; background: #fff; border-left: 4px solid #3498db; border-radius: 0 4px 4px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .event.landmark { border-left-color: #e74c3c; }
        .event.restaurant { border-left-color: #f39c12; }
        .event.hotel { border-left-color: #9b59b6; }
        .event.activity { border-left-color: #2ecc71; }
        .event.transit { border-left-color: #95a5a6; }
        .event-header { display: flex; justify-content: space-between; align-items: center; }
        .event-time { color: #666; font-size: 0.9em; }
        .event-sources { font-size: 0.8em; color: #999; }
        .event-photos { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 10px; }
        .event-photos img { max-width: 250px; max-height: 200px; border-radius: 4px; object-fit: cover; }
        .event-notes { margin-top: 0.5em; padding: 0.5em; background: #fffbea; border-radius: 4px; font-style: italic; }
        .expense-summary { margin: 2em 0; }
        .expense-summary table { width: 100%; border-collapse: collapse; }
        .expense-summary th, .expense-summary td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }
        .expense-summary th { background: #f8f9fa; }
        .accommodations { margin: 2em 0; }
        .accommodation { padding: 0.5em 0; border-bottom: 1px solid #eee; }
        {% block extra_css %}{% endblock %}
    </style>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Create detailed record template**

```html
<!-- src/post_trip_summary/templates/detailed_record.html -->
{% extends "base.html" %}
{% block title %}{{ trip.name }} — Detailed Record{% endblock %}

{% block content %}
<div class="trip-header">
    <h1>{{ trip.name }}</h1>
    <p class="dates">{{ trip.date_range[0].strftime('%B %d') }} — {{ trip.date_range[1].strftime('%B %d, %Y') }}</p>
</div>

{% for day in trip.days %}
{% if day.events %}
<div class="day-section">
    <h2>Day {{ loop.index }}: {{ day.date.strftime('%A, %B %d') }}</h2>

    {% for event in day.events %}
    <div class="event {{ event.type }}">
        <div class="event-header">
            <h3>{{ event.name }}</h3>
            <span class="event-time">{{ event.time_range[0] | ftime }} — {{ event.time_range[1] | ftime }}</span>
        </div>
        {% if event.description %}
        <p>{{ event.description }}</p>
        {% endif %}
        {% if event.notes %}
        <div class="event-notes">{{ event.notes }}</div>
        {% endif %}
        {% set highlights = event.photos | selectattr('is_highlight') | list %}
        {% if highlights %}
        <div class="event-photos">
            {% for photo in highlights %}
            <img src="photos/{{ photo.path.name }}" alt="{{ photo.ai_description or event.name }}" title="{{ photo.ai_description or '' }}">
            {% endfor %}
        </div>
        {% endif %}
        <div class="event-sources">Sources: {{ event.sources | join(', ') }}</div>
    </div>
    {% endfor %}
</div>
{% endif %}
{% endfor %}

{% if trip.accommodations %}
<div class="accommodations">
    <h2>Accommodations</h2>
    {% for acc in trip.accommodations %}
    <div class="accommodation">
        <strong>{{ acc.name }}</strong> — {{ acc.location.city }}, {{ acc.location.country }}<br>
        {{ acc.check_in.strftime('%b %d') }} to {{ acc.check_out.strftime('%b %d, %Y') }}
        {% if acc.location.address %}<br>{{ acc.location.address }}{% endif %}
    </div>
    {% endfor %}
</div>
{% endif %}

{% if trip.expenses %}
<div class="expense-summary">
    <h2>Expenses</h2>
    <table>
        <thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th>Amount</th></tr></thead>
        <tbody>
        {% for exp in trip.expenses | sort(attribute='date') %}
        <tr>
            <td>{{ exp.date.strftime('%b %d') }}</td>
            <td>{{ exp.merchant }}</td>
            <td>{{ exp.category or '—' }}</td>
            <td>{{ exp.currency }} {{ '%.2f' | format(exp.amount) }}</td>
        </tr>
        {% endfor %}
        <tr style="font-weight:bold; border-top: 2px solid #333;">
            <td colspan="3">Total</td>
            <td>{{ trip.expenses[0].currency if trip.expenses else '' }} {{ '%.2f' | format(trip.expenses | sum(attribute='amount')) }}</td>
        </tr>
        </tbody>
    </table>
</div>
{% endif %}
{% endblock %}
```

- [ ] **Step 3: Create shareable summary template**

```html
<!-- src/post_trip_summary/templates/shareable_summary.html -->
{% extends "base.html" %}
{% block title %}{{ trip.name }}{% endblock %}
{% block extra_css %}
@media print { .page-break { page-break-before: always; } }
body { max-width: 800px; }
.hero { text-align: center; margin: 2em 0; }
.hero img { max-width: 100%; max-height: 400px; border-radius: 8px; }
.highlight { margin: 1.5em 0; display: flex; gap: 1em; align-items: flex-start; }
.highlight img { max-width: 300px; border-radius: 4px; flex-shrink: 0; }
.highlight-text { flex: 1; }
.stats { display: flex; flex-wrap: wrap; gap: 1em; justify-content: center; margin: 2em 0; }
.stat { text-align: center; padding: 1em; background: #f8f9fa; border-radius: 8px; min-width: 120px; }
.stat-number { font-size: 2em; font-weight: bold; color: #2c3e50; }
.stat-label { font-size: 0.9em; color: #666; }
{% endblock %}

{% block content %}
<div class="trip-header">
    <h1>{{ trip.name }}</h1>
    <p class="dates">{{ trip.date_range[0].strftime('%B %d') }} — {{ trip.date_range[1].strftime('%B %d, %Y') }}</p>
</div>

{% if map_image %}
<div class="hero">
    <img src="{{ map_image }}" alt="Trip route">
</div>
{% endif %}

<h2>Highlights</h2>
{% for event in highlights %}
<div class="highlight">
    {% if event.photos %}
    {% set hl = event.photos | selectattr('is_highlight') | first %}
    {% if hl %}
    <img src="photos/{{ hl.path.name }}" alt="{{ event.name }}">
    {% endif %}
    {% endif %}
    <div class="highlight-text">
        <h3>{{ event.name }}</h3>
        <p class="event-time">{{ event.time_range[0].strftime('%A, %B %d') }} — {{ event.time_range[0] | ftime }}</p>
        <p>{{ event.description }}</p>
    </div>
</div>
{% endfor %}

<div class="page-break"></div>
<h2>By the Numbers</h2>
<div class="stats">
    <div class="stat"><div class="stat-number">{{ stats.days }}</div><div class="stat-label">Days</div></div>
    <div class="stat"><div class="stat-number">{{ stats.events }}</div><div class="stat-label">Stops</div></div>
    <div class="stat"><div class="stat-number">{{ stats.photos }}</div><div class="stat-label">Photos</div></div>
    {% if stats.countries > 1 %}<div class="stat"><div class="stat-number">{{ stats.countries }}</div><div class="stat-label">Countries</div></div>{% endif %}
    {% if stats.cities > 1 %}<div class="stat"><div class="stat-number">{{ stats.cities }}</div><div class="stat-label">Cities</div></div>{% endif %}
</div>
{% endblock %}
```

- [ ] **Step 4: Create blog post template**

```html
<!-- src/post_trip_summary/templates/blog_post.html -->
<h1>{{ trip.name }}</h1>
<p><em>{{ trip.date_range[0].strftime('%B %d') }} — {{ trip.date_range[1].strftime('%B %d, %Y') }}</em></p>

{% for event in highlights %}
<h2>{{ event.name }}</h2>
<p>{{ event.time_range[0].strftime('%A, %B %d') }}</p>
{% if event.photos %}
{% set hl = event.photos | selectattr('is_highlight') | first %}
{% if hl %}
<p><img src="photos/{{ hl.path.name }}" alt="{{ event.name }}" style="max-width:100%;"></p>
{% endif %}
{% endif %}
<p>{{ event.description }}</p>
{% if event.notes %}
<blockquote>{{ event.notes }}</blockquote>
{% endif %}
{% endfor %}
```

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/templates/
git commit -m "feat: add Jinja2 templates for detailed record, shareable summary, and blog post"
```

---

### Task 22: Output generators

**Files:**
- Create: `src/post_trip_summary/output/__init__.py`
- Create: `src/post_trip_summary/output/detailed_record.py`
- Create: `src/post_trip_summary/output/shareable_pdf.py`
- Create: `src/post_trip_summary/output/blog_post.py`
- Create: `src/post_trip_summary/output/photo_prep.py`
- Create: `tests/test_output.py`

- [ ] **Step 1: Create output package init**

```python
# src/post_trip_summary/output/__init__.py
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_output.py
from datetime import date, datetime
from pathlib import Path
from post_trip_summary.models import Trip, Day, Event, Photo, Location, Expense
from post_trip_summary.output.detailed_record import generate_detailed_record
from post_trip_summary.output.shareable_pdf import compute_stats, select_highlights
from post_trip_summary.output.photo_prep import collect_highlight_photos


def _trip() -> Trip:
    loc = Location(lat=48.858, lon=2.294, name="Eiffel Tower", address=None, city="Paris", country="France")
    photo = Photo(path=Path("/photos/img001.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294), is_highlight=True, ai_description="Eiffel Tower view")
    event = Event(id="day01-event01", type="landmark", name="Eiffel Tower",
                  time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
                  location=loc, photos=[photo], description="Visit to Eiffel Tower", notes="Amazing!", sources=["exif", "itinerary"])
    return Trip(
        name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 7)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
        expenses=[Expense(date=date(2026, 3, 5), amount=87.5, currency="EUR", merchant="Cafe", source="credit_card")],
    )


def test_generate_detailed_record(tmp_path):
    trip = _trip()
    output_path = tmp_path / "record.html"
    generate_detailed_record(trip, output_path)
    assert output_path.exists()
    content = output_path.read_text()
    assert "Paris 2026" in content
    assert "Eiffel Tower" in content


def test_compute_stats():
    trip = _trip()
    stats = compute_stats(trip)
    assert stats["days"] == 3
    assert stats["photos"] == 1
    assert stats["events"] == 1


def test_select_highlights_top_events():
    trip = _trip()
    highlights = select_highlights(trip, max_count=10)
    assert len(highlights) >= 1
    assert highlights[0].name == "Eiffel Tower"


def test_collect_highlight_photos():
    trip = _trip()
    photos = collect_highlight_photos(trip)
    assert len(photos) == 1
    assert photos[0].is_highlight
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_output.py -v`
Expected: FAIL

- [ ] **Step 4: Implement photo preparation**

```python
# src/post_trip_summary/output/photo_prep.py
"""Prepare highlight photos for output (resize and copy)."""
from pathlib import Path
from PIL import Image

from post_trip_summary.models import Trip, Photo

MAX_WIDTH = 1920


def collect_highlight_photos(trip: Trip) -> list[Photo]:
    """Gather all highlight photos from the trip."""
    highlights = []
    for day in trip.days:
        for event in day.events:
            for photo in event.photos:
                if photo.is_highlight:
                    highlights.append(photo)
    return highlights


def prepare_photos(trip: Trip, output_dir: Path) -> None:
    """Resize and copy highlight photos to output/photos/."""
    photos_dir = output_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    for photo in collect_highlight_photos(trip):
        src = photo.path
        dest = photos_dir / src.name
        if not src.exists():
            continue
        try:
            img = Image.open(src)
            if img.width > MAX_WIDTH:
                ratio = MAX_WIDTH / img.width
                new_size = (MAX_WIDTH, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            img.save(dest, quality=85)
        except Exception:
            # Fall back to simple copy
            import shutil
            shutil.copy2(src, dest)
```

- [ ] **Step 5: Implement detailed record generator**

```python
# src/post_trip_summary/output/detailed_record.py
"""Generate the detailed HTML trip record."""
from pathlib import Path
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip


def _format_time_filter(dt):
    """Jinja2 filter for cross-platform time formatting."""
    try:
        return dt.strftime("%#I:%M %p")  # Windows
    except ValueError:
        return dt.strftime("%-I:%M %p")  # Unix


def generate_detailed_record(trip: Trip, output_path: Path) -> None:
    """Render the detailed record HTML."""
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    env.filters["ftime"] = _format_time_filter
    template = env.get_template("detailed_record.html")
    html = template.render(trip=trip)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
```

- [ ] **Step 6: Implement shareable PDF generator**

```python
# src/post_trip_summary/output/shareable_pdf.py
"""Generate the shareable PDF summary."""
from pathlib import Path
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip, Event


def compute_stats(trip: Trip) -> dict:
    """Compute fun stats for the summary."""
    all_events = [e for d in trip.days for e in d.events]
    all_photos = [p for e in all_events for p in e.photos]
    cities = {e.location.city for e in all_events if e.location.city}
    countries = {e.location.country for e in all_events if e.location.country}
    return {
        "days": (trip.date_range[1] - trip.date_range[0]).days + 1,
        "events": len(all_events),
        "photos": len(all_photos),
        "cities": len(cities),
        "countries": len(countries),
    }


def select_highlights(trip: Trip, max_count: int = 10) -> list[Event]:
    """Select the top events for the shareable summary."""
    all_events = [e for d in trip.days for e in d.events if e.type != "transit"]
    # Prefer events with descriptions and highlight photos
    scored = []
    for event in all_events:
        score = 0
        if event.description:
            score += 2
        if any(p.is_highlight for p in event.photos):
            score += 2
        if len(event.sources) >= 2:
            score += 1
        if event.notes:
            score += 1
        scored.append((score, event))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [event for _, event in scored[:max_count]]


def generate_shareable_pdf(trip: Trip, output_path: Path, map_image: str | None = None) -> None:
    """Render the shareable summary and convert to PDF."""
    from post_trip_summary.output.detailed_record import _format_time_filter
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    env.filters["ftime"] = _format_time_filter
    template = env.get_template("shareable_summary.html")

    highlights = select_highlights(trip)
    stats = compute_stats(trip)

    html = template.render(trip=trip, highlights=highlights, stats=stats, map_image=map_image)

    # Write HTML first
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")

    # Convert to PDF
    try:
        from weasyprint import HTML
        HTML(string=html, base_url=str(output_path.parent)).write_pdf(output_path)
    except Exception as e:
        import click
        click.echo(f"Warning: PDF generation failed ({e}). HTML version saved at {html_path}")
```

- [ ] **Step 7: Implement blog post generator**

```python
# src/post_trip_summary/output/blog_post.py
"""Generate blog-ready HTML."""
from pathlib import Path
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip
from post_trip_summary.output.shareable_pdf import select_highlights


def generate_blog_post(trip: Trip, output_path: Path) -> None:
    """Render a blog-friendly HTML file."""
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))
    template = env.get_template("blog_post.html")
    highlights = select_highlights(trip)
    html = template.render(trip=trip, highlights=highlights)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_output.py -v`
Expected: All 4 tests PASS

- [ ] **Step 9: Commit**

```bash
git add src/post_trip_summary/output/ tests/test_output.py
git commit -m "feat: add output generators (detailed record, PDF, blog post, photo prep)"
```

---

### Task 23: Preview server

**Files:**
- Create: `src/post_trip_summary/preview/__init__.py`
- Create: `src/post_trip_summary/preview/server.py`
- Create: `tests/test_preview.py`

- [ ] **Step 1: Create preview package init**

```python
# src/post_trip_summary/preview/__init__.py
```

- [ ] **Step 2: Write failing test**

```python
# tests/test_preview.py
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from post_trip_summary.models import Trip, Day, Event, Photo, Location
from post_trip_summary.preview.server import create_app


def _trip() -> Trip:
    loc = Location(lat=48.858, lon=2.294, name="Eiffel Tower", address=None, city="Paris", country="France")
    photo = Photo(path=Path("/photos/img001.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294), is_highlight=True, ai_description="Tower")
    event = Event(id="d1e1", type="landmark", name="Eiffel Tower",
                  time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
                  location=loc, photos=[photo], description="Visit", notes="", sources=["exif"])
    return Trip(name="Paris 2026", date_range=(date(2026, 3, 5), date(2026, 3, 7)),
                days=[Day(date=date(2026, 3, 5), events=[event])])


def test_preview_detailed_record():
    trip = _trip()
    app = create_app(trip)
    client = TestClient(app)
    response = client.get("/detailed")
    assert response.status_code == 200
    assert "Paris 2026" in response.text


def test_preview_summary():
    trip = _trip()
    app = create_app(trip)
    client = TestClient(app)
    response = client.get("/summary")
    assert response.status_code == 200
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_preview.py -v`
Expected: FAIL

- [ ] **Step 4: Implement preview server**

```python
# src/post_trip_summary/preview/server.py
"""Local FastAPI preview server for trip outputs."""
import webbrowser
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from jinja2 import Environment, PackageLoader

from post_trip_summary.models import Trip
from post_trip_summary.output.shareable_pdf import select_highlights, compute_stats


def create_app(trip: Trip) -> FastAPI:
    """Create a FastAPI app for previewing trip outputs."""
    app = FastAPI(title="Post-Trip Summary Preview")
    env = Environment(loader=PackageLoader("post_trip_summary", "templates"))

    @app.get("/", response_class=HTMLResponse)
    def index():
        return f"""<html><body>
        <h1>Preview: {trip.name}</h1>
        <ul>
            <li><a href="/detailed">Detailed Record</a></li>
            <li><a href="/summary">Shareable Summary</a></li>
            <li><a href="/blog">Blog Post</a></li>
        </ul>
        </body></html>"""

    @app.get("/detailed", response_class=HTMLResponse)
    def detailed():
        template = env.get_template("detailed_record.html")
        return template.render(trip=trip)

    @app.get("/summary", response_class=HTMLResponse)
    def summary():
        template = env.get_template("shareable_summary.html")
        highlights = select_highlights(trip)
        stats = compute_stats(trip)
        return template.render(trip=trip, highlights=highlights, stats=stats, map_image=None)

    @app.get("/blog", response_class=HTMLResponse)
    def blog():
        template = env.get_template("blog_post.html")
        highlights = select_highlights(trip)
        return template.render(trip=trip, highlights=highlights)

    return app


def run_preview(trip: Trip, port: int = 8765) -> None:
    """Start the preview server and open browser."""
    import uvicorn
    import click

    app = create_app(trip)
    click.echo(f"\nPreview server starting at http://localhost:{port}")
    click.echo("Press Ctrl+C to stop.\n")
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_preview.py -v`
Expected: Both tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/post_trip_summary/preview/ tests/test_preview.py
git commit -m "feat: add FastAPI preview server for trip outputs"
```

---

### Task 24: Wire pipeline into CLI

**Files:**
- Modify: `src/post_trip_summary/cli.py`
- Create: `tests/test_cli_pipeline.py`

- [ ] **Step 1: Write failing test for resume pipeline flow**

```python
# tests/test_cli_pipeline.py
from click.testing import CliRunner
from post_trip_summary.cli import cli


def test_resume_unknown_session(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["resume", "nonexistent", "--base-dir", str(tmp_path)])
    assert result.exit_code != 0 or "not found" in result.output.lower() or "Error" in result.output


def test_generate_no_data(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["new", "Test Trip", "--base-dir", str(tmp_path)], input="/fake/path\n")
    result = runner.invoke(cli, ["generate", "test-trip", "--base-dir", str(tmp_path)])
    assert result.exit_code != 0 or "No data" in result.output or "no final" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_cli_pipeline.py -v`
Expected: FAIL (generate command not yet wired)

- [ ] **Step 3: Update CLI with full pipeline wiring**

Replace the `resume`, add `preview` and `generate` commands in `src/post_trip_summary/cli.py`:

```python
# src/post_trip_summary/cli.py
"""CLI entry point for Post-Trip Summary."""
import click
from pathlib import Path

from post_trip_summary.config import (
    create_session, load_session, list_sessions, delete_session, DEFAULT_BASE_DIR,
)


@click.group()
@click.version_option()
def cli():
    """Post-Trip Summary — Generate trip summaries from vacation photos and travel data."""
    pass


@cli.command()
@click.argument("name")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def new(name: str, base_dir: Path | None):
    """Create a new trip session."""
    base = base_dir or DEFAULT_BASE_DIR
    session = create_session(name, base_dir=base)
    click.echo(f"Created session '{session.name}' ({session.slug})")
    photos_path = click.prompt("Where are your photos?", type=str)
    session.inputs["photos"] = photos_path
    session.save()
    click.echo(f"Session saved. Run 'post-trip-summary resume {session.slug}' to continue.")


@cli.command("list")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def list_cmd(base_dir: Path | None):
    """List all trip sessions."""
    base = base_dir or DEFAULT_BASE_DIR
    sessions = list_sessions(base_dir=base)
    if not sessions:
        click.echo("No sessions found.")
        return
    for s in sessions:
        click.echo(f"  {s.slug}  ({s.name})  stage: {s.current_stage}")


@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def delete(slug: str, base_dir: Path | None):
    """Delete a trip session."""
    base = base_dir or DEFAULT_BASE_DIR
    if click.confirm(f"Delete session '{slug}'? This cannot be undone"):
        delete_session(slug, base_dir=base)
        click.echo(f"Deleted session '{slug}'.")


@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def resume(slug: str, base_dir: Path | None):
    """Resume a trip session from where you left off."""
    base = base_dir or DEFAULT_BASE_DIR
    try:
        session = load_session(slug, base_dir=base)
    except FileNotFoundError:
        click.echo(f"Error: Session '{slug}' not found.")
        raise SystemExit(1)

    click.echo(f"Resuming '{session.name}' at stage: {session.current_stage}")

    from post_trip_summary.serialization import save_trip, load_trip

    # Stage 1: Ingest
    if session.current_stage in ("new", "ingest"):
        click.echo("\n═══ Stage 1: Ingesting data ═══")
        trip_data = _run_ingest(session)
        session.current_stage = "ingest"
        session.save()

    # Stage 2: Build skeleton
    if session.current_stage == "ingest":
        click.echo("\n═══ Stage 2: Building trip skeleton ═══")
        from post_trip_summary.pipeline.skeleton import build_skeleton
        trip_data = _load_trip_data(session)
        trip = build_skeleton(
            trip_data,
            gap_minutes=session.settings["cluster_time_gap_minutes"],
            distance_meters=session.settings["cluster_distance_meters"],
        )
        trip.name = session.name
        save_trip(trip, session.stage_file("skeleton"))
        session.current_stage = "skeleton"
        session.save()
        click.echo(f"Skeleton built: {sum(len(d.events) for d in trip.days)} events across {len(trip.days)} days")

    # Stage 3: Review skeleton
    if session.current_stage == "skeleton":
        trip = load_trip(session.stage_file("skeleton"))
        from post_trip_summary.pipeline.review_skeleton import review_skeleton
        trip = review_skeleton(trip)
        save_trip(trip, session.stage_file("skeleton_reviewed"))
        session.current_stage = "skeleton_reviewed"
        session.save()

    # Stage 4: Enrich
    if session.current_stage == "skeleton_reviewed":
        trip = load_trip(session.stage_file("skeleton_reviewed"))
        from post_trip_summary.pipeline.enrich import enrich_trip
        trip = enrich_trip(trip)
        save_trip(trip, session.stage_file("enriched"))
        session.current_stage = "enriched"
        session.save()

    # Stage 5: Review details
    if session.current_stage == "enriched":
        trip = load_trip(session.stage_file("enriched"))
        from post_trip_summary.pipeline.review_details import review_details
        trip = review_details(trip)
        save_trip(trip, session.stage_file("final"))
        session.current_stage = "final"
        session.save()

    click.echo(f"\nSession at stage: {session.current_stage}")
    click.echo(f"Run 'post-trip-summary preview {slug}' to preview, or 'post-trip-summary generate {slug}' to create outputs.")


@cli.command("add-input")
@click.argument("slug")
@click.option("--photos", type=click.Path(exists=True, path_type=Path))
@click.option("--excel", type=click.Path(exists=True, path_type=Path))
@click.option("--credit-card", type=click.Path(exists=True, path_type=Path))
@click.option("--google-maps", type=click.Path(exists=True, path_type=Path))
@click.option("--apple-health", type=click.Path(exists=True, path_type=Path))
@click.option("--dayone", type=click.Path(exists=True, path_type=Path))
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def add_input(slug: str, base_dir: Path | None, **inputs):
    """Add input data sources to a session."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    for key, value in inputs.items():
        if key == "base_dir":
            continue
        if value is not None:
            session.inputs[key.replace("-", "_")] = str(value)
            click.echo(f"  Added {key}: {value}")
    session.save()


@cli.command()
@click.argument("slug")
@click.option("--port", default=8765, help="Preview server port")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def preview(slug: str, port: int, base_dir: Path | None):
    """Preview trip outputs in browser."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    stage = session.current_stage
    if stage not in ("enriched", "final", "generated"):
        click.echo(f"No data to preview yet (stage: {stage}). Run 'resume' first.")
        raise SystemExit(1)
    from post_trip_summary.serialization import load_trip
    trip_file = session.stage_file("final") if session.stage_file("final").exists() else session.stage_file("enriched")
    trip = load_trip(trip_file)
    from post_trip_summary.preview.server import run_preview
    run_preview(trip, port=port)


@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def generate(slug: str, base_dir: Path | None):
    """Generate final output files."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    final_file = session.stage_file("final")
    if not final_file.exists():
        click.echo("No final data. Run 'resume' to complete the pipeline first.")
        raise SystemExit(1)

    from post_trip_summary.serialization import load_trip
    from post_trip_summary.output.photo_prep import prepare_photos
    from post_trip_summary.output.detailed_record import generate_detailed_record
    from post_trip_summary.output.shareable_pdf import generate_shareable_pdf
    from post_trip_summary.output.blog_post import generate_blog_post

    trip = load_trip(final_file)
    output_dir = session.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"\n═══ Generating outputs ═══")

    click.echo("  Preparing photos...")
    prepare_photos(trip, output_dir)

    click.echo("  Generating detailed record...")
    generate_detailed_record(trip, output_dir / "detailed-record.html")

    click.echo("  Generating route map...")
    map_path = _generate_static_map(trip, output_dir)

    click.echo("  Generating shareable summary...")
    generate_shareable_pdf(trip, output_dir / "shareable-summary.pdf", map_image=map_path)

    click.echo("  Generating blog post...")
    generate_blog_post(trip, output_dir / "blog-post.html")

    session.current_stage = "generated"
    session.save()
    click.echo(f"\nOutputs saved to: {output_dir}")


def _generate_static_map(trip, output_dir) -> str | None:
    """Generate a static map image showing major stops. Returns relative path or None."""
    try:
        from staticmap import StaticMap, CircleMarker
        m = StaticMap(800, 400)
        for day in trip.days:
            for event in day.events:
                if event.location.lat and event.location.lon:
                    m.add_marker(CircleMarker((event.location.lon, event.location.lat), "#e74c3c", 8))
        if m.markers:
            map_path = output_dir / "route-map.png"
            image = m.render()
            image.save(str(map_path))
            return "route-map.png"
    except Exception as e:
        click.echo(f"  Warning: Map generation failed ({e}). Skipping.")
    return None


def _run_ingest(session) -> dict:
    """Run all ingest modules based on configured inputs."""
    import json

    trip_data = {
        "photos": [],
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }

    # Photos
    photos_path = session.inputs.get("photos")
    if photos_path:
        click.echo(f"  Scanning photos: {photos_path}")
        from post_trip_summary.pipeline.ingest.photos import ingest_photos
        trip_data["photos"] = ingest_photos(Path(photos_path))
        click.echo(f"    Found {len(trip_data['photos'])} photos")

    # Excel
    excel_path = session.inputs.get("excel")
    if excel_path:
        click.echo(f"  Parsing Excel: {excel_path}")
        from post_trip_summary.pipeline.ingest.excel import ingest_excel
        excel_data = ingest_excel(Path(excel_path))
        trip_data["accommodations"] = excel_data["accommodations"]
        trip_data["transits"] = excel_data["transits"]
        trip_data["activities"] = excel_data["activities"]
        trip_data["expenses"].extend(excel_data["expenses"])

    # Credit card
    cc_path = session.inputs.get("credit_card")
    if cc_path:
        click.echo(f"  Parsing credit card CSV: {cc_path}")
        from post_trip_summary.pipeline.ingest.credit_card import ingest_credit_card
        trip_data["expenses"].extend(ingest_credit_card(Path(cc_path)))

    # Google Maps
    gm_path = session.inputs.get("google_maps")
    if gm_path:
        click.echo(f"  Parsing Google Maps timeline: {gm_path}")
        from post_trip_summary.pipeline.ingest.google_maps import ingest_google_maps
        trip_data["google_maps"] = ingest_google_maps(Path(gm_path))

    # Apple Health
    ah_path = session.inputs.get("apple_health")
    if ah_path:
        click.echo(f"  Parsing Apple Health: {ah_path}")
        from post_trip_summary.pipeline.ingest.apple_health import ingest_apple_health
        trip_data["apple_health"] = ingest_apple_health(Path(ah_path))

    # Day One
    do_path = session.inputs.get("dayone")
    if do_path:
        click.echo(f"  Parsing Day One: {do_path}")
        from post_trip_summary.pipeline.ingest.dayone import ingest_dayone
        trip_data["dayone"] = ingest_dayone(Path(do_path))

    # Save raw trip data
    data_file = session.session_dir / "trip_data.json"
    # Serialize trip_data (contains model objects, need custom handling)
    from post_trip_summary.serialization import encode_value
    data_file.write_text(json.dumps(encode_value(trip_data), indent=2), encoding="utf-8")

    return trip_data


def _load_trip_data(session) -> dict:
    """Load raw trip data from disk."""
    import json
    from post_trip_summary.serialization import decode_value
    data_file = session.session_dir / "trip_data.json"
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    return decode_value(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/test_cli_pipeline.py tests/test_cli.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/cli.py tests/test_cli_pipeline.py
git commit -m "feat: wire full pipeline into CLI (resume, preview, generate commands)"
```

---

### Task 25: Run full test suite

- [ ] **Step 1: Run all tests**

Run: `cd C:/Users/matth/OneDrive/Documents/Projects/PostTripSummary && .venv/Scripts/python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Fix any failures and re-run**

If any tests fail, fix the issues and re-run until green.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: ensure all tests pass across full test suite"
```
