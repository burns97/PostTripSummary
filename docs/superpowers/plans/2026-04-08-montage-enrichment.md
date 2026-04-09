# Montage-Based Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-photo enrichment with montage-first approach that produces broader event descriptions with quick and thorough modes.

**Architecture:** Build a montage generation utility (PIL grid of thumbnails), add new prompt templates for montage analysis and narrative synthesis, then rewrite the enrichment pipeline to use montages as the primary input. Events with <=3 photos skip montages and send photos individually. Two modes: quick (montage only) and thorough (montage + individual highlights + narrative synthesis).

**Tech Stack:** Python 3.10+, PIL/Pillow, Gemini Flash API (via google-genai), pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/post_trip_summary/vision/montage.py` | Create | Montage grid generation: temporal sampling, thumbnail grid, number labels |
| `tests/test_montage.py` | Create | Montage unit tests |
| `src/post_trip_summary/models.py` | Modify | Add `summary` field to Event |
| `src/post_trip_summary/vision/prompts.py` | Modify | Add `montage` and `narrative` prompt templates |
| `src/post_trip_summary/vision/client.py` | Modify | Add `analyze_montage` to VisionProvider ABC |
| `src/post_trip_summary/vision/gemini.py` | Modify | Implement `analyze_montage` for Gemini |
| `src/post_trip_summary/pipeline/enrich.py` | Modify | Rewrite enrichment with montage-based quick/thorough modes |
| `src/post_trip_summary/server/app.py` | Modify | Update cost estimate API for new modes |
| `src/post_trip_summary/templates/enrich.html` | Modify | Update buttons to quick/thorough/skip |
| `src/post_trip_summary/server/compute.py` | Modify | Pass new mode values |

---

### Task 1: Montage Generation Utility

**Files:**
- Create: `src/post_trip_summary/vision/montage.py`
- Create: `tests/test_montage.py`

- [ ] **Step 1: Write failing tests for montage generation**

```python
# tests/test_montage.py
"""Tests for vision.montage -- thumbnail grid generation."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from post_trip_summary.models import Photo


def _photo(name: str, minutes: int = 0) -> Photo:
    """Create a test Photo with a fake path and timestamp."""
    return Photo(
        path=Path(f"/fake/{name}.jpg"),
        timestamp=datetime(2026, 1, 1, 10, minutes),
        gps=None,
    )


def _make_test_image(path: Path, color: str = "red", size: tuple = (800, 600)):
    """Create a real test image file."""
    img = Image.new("RGB", size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG")


class TestTemporalSample:
    def test_returns_all_when_under_max(self):
        from post_trip_summary.vision.montage import _temporal_sample
        photos = [_photo("a", 0), _photo("b", 5), _photo("c", 10)]
        result = _temporal_sample(photos, max_count=5)
        assert len(result) == 3

    def test_samples_evenly_when_over_max(self):
        from post_trip_summary.vision.montage import _temporal_sample
        photos = [_photo(f"p{i}", i) for i in range(30)]
        result = _temporal_sample(photos, max_count=10)
        assert len(result) == 10
        # First and last should be included
        assert result[0].path.name == "p0.jpg"
        assert result[-1].path.name == "p29.jpg"

    def test_empty_list(self):
        from post_trip_summary.vision.montage import _temporal_sample
        assert _temporal_sample([], max_count=5) == []


class TestBuildMontage:
    def test_produces_valid_jpeg(self, tmp_path):
        from post_trip_summary.vision.montage import build_montage
        photos = []
        for i in range(6):
            p = _photo(f"img{i}", i)
            real_path = tmp_path / f"img{i}.jpg"
            _make_test_image(real_path)
            p.path = real_path
            photos.append(p)

        data, photo_map = build_montage(photos)
        img = Image.open(BytesIO(data))
        assert img.format == "JPEG"
        assert len(photo_map) == 6

    def test_respects_thumb_size(self, tmp_path):
        from post_trip_summary.vision.montage import build_montage
        photos = []
        for i in range(4):
            p = _photo(f"img{i}", i)
            real_path = tmp_path / f"img{i}.jpg"
            _make_test_image(real_path)
            p.path = real_path
            photos.append(p)

        data, _ = build_montage(photos, thumb_size=128, cols=2)
        img = Image.open(BytesIO(data))
        # 2 cols x 128px = 256 wide, 2 rows x 128px = 256 tall (approx, plus labels)
        assert img.width == 2 * 128
        assert img.height >= 2 * 128  # labels add some height

    def test_max_count_limits_photos(self, tmp_path):
        from post_trip_summary.vision.montage import build_montage
        photos = []
        for i in range(25):
            p = _photo(f"img{i}", i)
            real_path = tmp_path / f"img{i}.jpg"
            _make_test_image(real_path)
            p.path = real_path
            photos.append(p)

        data, photo_map = build_montage(photos, max_count=10)
        assert len(photo_map) == 10

    def test_photo_map_maps_grid_index_to_photo(self, tmp_path):
        from post_trip_summary.vision.montage import build_montage
        photos = []
        for i in range(3):
            p = _photo(f"img{i}", i)
            real_path = tmp_path / f"img{i}.jpg"
            _make_test_image(real_path)
            p.path = real_path
            photos.append(p)

        _, photo_map = build_montage(photos)
        # photo_map is {1: Photo, 2: Photo, 3: Photo} (1-indexed)
        assert set(photo_map.keys()) == {1, 2, 3}
        assert photo_map[1].path.name == "img0.jpg"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_montage.py -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'post_trip_summary.vision.montage'`

- [ ] **Step 3: Implement montage generation**

```python
# src/post_trip_summary/vision/montage.py
"""Thumbnail grid (montage) generation for vision API analysis."""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from post_trip_summary.models import Photo


def _temporal_sample(photos: list[Photo], max_count: int) -> list[Photo]:
    """Sample photos evenly across time range, always including first and last."""
    if len(photos) <= max_count:
        return list(photos)
    if max_count <= 0:
        return []
    if max_count == 1:
        return [photos[0]]

    step = (len(photos) - 1) / (max_count - 1)
    indices = [round(i * step) for i in range(max_count)]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            unique.append(idx)
    return [photos[i] for i in unique]


def build_montage(
    photos: list[Photo],
    thumb_size: int = 256,
    cols: int = 5,
    max_count: int = 20,
) -> tuple[bytes, dict[int, Photo]]:
    """Build a numbered thumbnail grid from a list of photos.

    Args:
        photos: Photos to include in the montage.
        thumb_size: Width and height of each thumbnail cell in pixels.
        cols: Number of columns in the grid.
        max_count: Maximum photos to include. If more, samples by temporal spread.

    Returns:
        Tuple of (JPEG bytes, photo_map) where photo_map is
        {1-indexed grid number: Photo} so the caller can map
        Gemini's picks back to Photo objects.
    """
    sampled = _temporal_sample(photos, max_count)
    if not sampled:
        return b"", {}

    rows = (len(sampled) + cols - 1) // cols
    label_height = 20
    cell_height = thumb_size + label_height

    grid_w = cols * thumb_size
    grid_h = rows * cell_height
    grid = Image.new("RGB", (grid_w, grid_h), (0, 0, 0))
    draw = ImageDraw.Draw(grid)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()

    photo_map: dict[int, Photo] = {}

    for idx, photo in enumerate(sampled):
        grid_num = idx + 1  # 1-indexed for display
        photo_map[grid_num] = photo

        col = idx % cols
        row = idx // cols
        x = col * thumb_size
        y = row * cell_height

        # Draw label
        draw.text((x + 4, y + 2), str(grid_num), fill=(255, 255, 255), font=font)

        # Draw thumbnail
        try:
            img = Image.open(photo.path)
            img.thumbnail((thumb_size, thumb_size - label_height))
            # Center thumbnail in cell below label
            paste_x = x + (thumb_size - img.width) // 2
            paste_y = y + label_height + (thumb_size - label_height - img.height) // 2
            grid.paste(img, (paste_x, paste_y))
        except Exception:
            # Draw placeholder for corrupt/missing images
            draw.rectangle(
                [x, y + label_height, x + thumb_size - 1, y + cell_height - 1],
                fill=(40, 40, 40),
            )
            draw.text((x + thumb_size // 2 - 5, y + cell_height // 2), "?", fill=(100, 100, 100), font=font)

    buf = BytesIO()
    grid.save(buf, format="JPEG", quality=85)
    return buf.getvalue(), photo_map
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_montage.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/vision/montage.py tests/test_montage.py
git commit -m "Add montage grid generation utility"
```

---

### Task 2: Add `summary` Field to Event Model

**Files:**
- Modify: `src/post_trip_summary/models.py:30-41`

- [ ] **Step 1: Add summary field**

In `src/post_trip_summary/models.py`, add `summary` field to Event after `description`:

```python
@dataclass
class Event:
    id: str
    type: str  # landmark, restaurant, hotel, activity, transit, unknown
    name: str
    time_range: tuple[datetime, datetime]
    location: Location
    photos: list[Photo] = field(default_factory=list)
    description: str = ""
    summary: str = ""
    notes: str = ""
    sources: list[str] = field(default_factory=list)
    name_candidates: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 2: Run existing tests to verify nothing breaks**

Run: `python -m pytest tests/ -v`
Expected: All existing tests PASS (summary defaults to empty string, serialization uses `__dict__` so it's automatic)

- [ ] **Step 3: Commit**

```bash
git add src/post_trip_summary/models.py
git commit -m "Add summary field to Event model"
```

---

### Task 3: Add Montage and Narrative Prompts

**Files:**
- Modify: `src/post_trip_summary/vision/prompts.py`
- Test: `tests/test_vision_prompts.py`

- [ ] **Step 1: Write failing tests for new prompts**

Add to `tests/test_vision_prompts.py`:

```python
def test_montage_prompt_requests_json():
    from post_trip_summary.vision.prompts import get_prompt
    prompt = get_prompt("montage", context="Location: Hobbiton", image_count=15)
    assert "JSON" in prompt or "json" in prompt
    assert "summary" in prompt
    assert "highlights" in prompt
    assert "15" in prompt


def test_narrative_prompt_requests_json():
    from post_trip_summary.vision.prompts import get_prompt
    prompt = get_prompt("narrative", context="Location: Hobbiton",
                        montage_summary="We toured Hobbiton.",
                        descriptions="1. A hobbit hole\n2. The Green Dragon")
    assert "JSON" in prompt or "json" in prompt
    assert "narrative" in prompt
    assert "We toured Hobbiton" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_vision_prompts.py::test_montage_prompt_requests_json tests/test_vision_prompts.py::test_narrative_prompt_requests_json -v`
Expected: FAIL -- `Unknown purpose: montage`

- [ ] **Step 3: Add prompt templates**

In `src/post_trip_summary/vision/prompts.py`, update `PURPOSES` and add to `_PROMPTS`:

```python
PURPOSES = ("landmark", "sign", "scene", "synthesize", "montage", "narrative")
```

Add to `_PROMPTS` dict:

```python
    "montage": """Here are {image_count} photos from a single event during a vacation trip, shown as a numbered grid.
{context}
Describe what was seen and done across these photos. Focus on the overall experience, not individual photos. 2-3 sentences, suitable for a trip summary.

Also pick up to 5 of the most interesting/representative photos by their grid number.

Respond with JSON only:
{{
  "summary": "factual 2-3 sentence summary of the event",
  "highlights": [3, 7, 12]
}}""",

    "narrative": """Here is a factual summary of an event, plus detailed descriptions of key photos:

Summary: {montage_summary}

Photo details:
{descriptions}
{context}
Write a 3-5 sentence journal-style narrative that brings this event to life. Blend the overview with specific details from the photos.

Respond with JSON only:
{{
  "narrative": "journal-style paragraph"
}}""",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vision_prompts.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/post_trip_summary/vision/prompts.py tests/test_vision_prompts.py
git commit -m "Add montage and narrative prompt templates"
```

---

### Task 4: Add `analyze_montage` to Vision Provider

**Files:**
- Modify: `src/post_trip_summary/vision/client.py:17-28`
- Modify: `src/post_trip_summary/vision/gemini.py`
- Test: `tests/test_vision_client.py`

- [ ] **Step 1: Write failing test for analyze_montage**

Add to `tests/test_vision_client.py`:

```python
def test_gemini_analyze_montage_mock(monkeypatch):
    """Test Gemini provider's analyze_montage with mocked API."""
    from unittest.mock import MagicMock
    from post_trip_summary.vision.gemini import GeminiProvider

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"summary": "Visited a movie set.", "highlights": [1, 3, 5]}'
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider.__new__(GeminiProvider)
    provider._client = mock_client
    provider._model = "gemini-2.5-flash"

    result = provider.analyze_montage(
        image_data=b"fake-jpeg",
        media_type="image/jpeg",
        purpose="montage",
        context="Location: Hobbiton",
        image_count=10,
    )
    assert result["summary"] == "Visited a movie set."
    assert result["highlights"] == [1, 3, 5]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vision_client.py::test_gemini_analyze_montage_mock -v`
Expected: FAIL -- `AttributeError: 'GeminiProvider' object has no attribute 'analyze_montage'`

- [ ] **Step 3: Add analyze_montage to VisionProvider ABC**

In `src/post_trip_summary/vision/client.py`, add to `VisionProvider` class after `synthesize`:

```python
    def analyze_montage(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "montage",
        context: str = "",
        image_count: int = 0,
    ) -> dict:
        """Analyze a montage image. Returns dict with 'summary' and 'highlights' keys."""
        raise NotImplementedError("Provider does not support montage analysis")
```

- [ ] **Step 4: Implement analyze_montage in GeminiProvider**

In `src/post_trip_summary/vision/gemini.py`, add method to `GeminiProvider`:

```python
    def analyze_montage(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "montage",
        context: str = "",
        image_count: int = 0,
        max_retries: int = 3,
    ) -> dict:
        """Send a montage image to Gemini and parse summary + highlights."""
        from google.genai import types
        from post_trip_summary.vision.prompts import get_prompt

        prompt = get_prompt(purpose, context=context, image_count=image_count)
        contents = [
            types.Part.from_bytes(data=image_data, mime_type=media_type),
            types.Part.from_text(text=prompt),
        ]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=1524,
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
        )

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                text = response.text
                try:
                    data = json.loads(text)
                    return {
                        "summary": data.get("summary", ""),
                        "highlights": data.get("highlights", []),
                    }
                except json.JSONDecodeError:
                    return {"summary": text, "highlights": []}

            except Exception as e:
                last_error = e
                error_str = str(e)

                if "429" not in error_str and "RESOURCE_EXHAUSTED" not in error_str:
                    raise

                if "limit: 0" in error_str:
                    raise QuotaExhaustedError(
                        "Gemini free tier quota exhausted."
                    ) from e

                if attempt < max_retries:
                    wait = min(2 ** attempt * 2, 60)
                    time.sleep(wait)

        raise last_error
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_vision_client.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/post_trip_summary/vision/client.py src/post_trip_summary/vision/gemini.py tests/test_vision_client.py
git commit -m "Add analyze_montage to vision providers"
```

---

### Task 5: Rewrite Enrichment Pipeline -- Quick Mode

**Files:**
- Modify: `src/post_trip_summary/pipeline/enrich.py`
- Create: `tests/test_enrich_montage.py`

- [ ] **Step 1: Write failing tests for quick mode**

```python
# tests/test_enrich_montage.py
"""Tests for montage-based enrichment pipeline."""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from post_trip_summary.models import Trip, Day, Event, Photo, Location


def _location():
    return Location(lat=0, lon=0, name="Test", address=None, city="Test", country="NZ")


def _photo(tmp_path, name: str, minutes: int = 0) -> Photo:
    path = tmp_path / f"{name}.jpg"
    Image.new("RGB", (100, 100), "red").save(path, "JPEG")
    return Photo(path=path, timestamp=datetime(2026, 1, 1, 10, minutes), gps=None)


def _trip_with_event(tmp_path, photo_count: int) -> Trip:
    photos = [_photo(tmp_path, f"p{i}", i) for i in range(photo_count)]
    event = Event(
        id="d01-e01", type="landmark", name="Hobbiton",
        time_range=(photos[0].timestamp, photos[-1].timestamp),
        location=_location(), photos=photos,
    )
    return Trip(
        name="Test", date_range=(datetime(2026, 1, 1).date(), datetime(2026, 1, 1).date()),
        days=[Day(date=datetime(2026, 1, 1).date(), events=[event])],
    )


class TestQuickMode:
    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_montage_sent_for_event_with_many_photos(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless

        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {
            "summary": "Toured the Hobbiton movie set.",
            "highlights": [1, 3, 5],
        }
        mock_create.return_value = mock_provider

        trip = _trip_with_event(tmp_path, photo_count=10)
        result = enrich_trip_headless(trip, mode="quick")

        event = result.days[0].events[0]
        assert event.summary == "Toured the Hobbiton movie set."
        assert event.description == "Toured the Hobbiton movie set."
        mock_provider.analyze_montage.assert_called_once()

    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_highlights_from_montage_picks(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless

        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {
            "summary": "A tour.",
            "highlights": [2, 4],
        }
        mock_create.return_value = mock_provider

        trip = _trip_with_event(tmp_path, photo_count=6)
        result = enrich_trip_headless(trip, mode="quick")

        event = result.days[0].events[0]
        highlighted = [p for p in event.photos if p.is_highlight]
        assert len(highlighted) == 2

    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_few_photos_skip_montage(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless

        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = MagicMock(
            description="A single photo.", landmark=None, confidence="medium"
        )
        mock_create.return_value = mock_provider

        trip = _trip_with_event(tmp_path, photo_count=2)
        result = enrich_trip_headless(trip, mode="quick")

        event = result.days[0].events[0]
        # Should use individual analyze, not analyze_montage
        mock_provider.analyze_montage.assert_not_called()
        assert mock_provider.analyze.call_count >= 1


class TestSkipMode:
    def test_skip_mode_selects_highlights_only(self, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless

        trip = _trip_with_event(tmp_path, photo_count=6)
        result = enrich_trip_headless(trip, mode="skip")

        event = result.days[0].events[0]
        assert event.summary == ""
        assert event.description == ""
        highlighted = [p for p in event.photos if p.is_highlight]
        assert len(highlighted) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_enrich_montage.py -v`
Expected: FAIL -- mode "quick" not recognized or montage not used

- [ ] **Step 3: Rewrite `enrich_trip_headless` with montage-based quick mode**

Replace the body of `enrich_trip_headless` in `src/post_trip_summary/pipeline/enrich.py`. Keep the existing `_select_highlights` and `_read_image` helpers. Replace the main function:

```python
def enrich_trip_headless(
    trip: Trip,
    mode: str = "quick",
    progress_callback=None,
) -> Trip:
    """Run vision enrichment without CLI interaction.

    Args:
        trip: The trip to enrich.
        mode: "quick" (montage summaries), "thorough" (montages + details + narrative),
              or "skip" (highlights only).
        progress_callback: Optional callable(phase, current, total, label).

    Returns:
        The enriched trip.
    """
    # Backward-compatible mode mapping
    mode_map = {"full": "thorough", "reduced": "quick"}
    mode = mode_map.get(mode, mode)

    def _progress(phase, current, total, label=""):
        if progress_callback:
            progress_callback(phase, current, total, label)

    all_events = [event for day in trip.days for event in day.events if event.photos]

    if mode == "skip":
        for event in all_events:
            _select_highlights(event.photos)
        _progress("done", 0, 0, "Skipped enrichment, highlights selected")
        return trip

    # Create vision provider
    vs = get_vision_settings()
    if not vs.get("api_key"):
        for event in all_events:
            _select_highlights(event.photos)
        _progress("done", 0, 0, "No API key; highlights selected only")
        return trip

    provider = create_provider(vs["provider"], api_key=vs.get("api_key"), model=vs.get("model"))

    from post_trip_summary.vision.gemini import QuotaExhaustedError
    from post_trip_summary.vision.montage import build_montage
    from post_trip_summary.vision.prompts import build_context

    event_count = len(all_events)
    analyzed = 0
    quota_exhausted = False

    for event_idx, event in enumerate(all_events, 1):
        if quota_exhausted:
            _select_highlights(event.photos)
            continue

        kept_photos = [p for p in event.photos if p.is_kept]
        if not kept_photos:
            continue

        loc = event.location
        context = build_context(
            timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
            city=loc.city if loc else "",
            country=loc.country if loc else "",
            poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
        )

        _progress("analyzing", analyzed, event_count,
                  f"[{event_idx}/{event_count}] {event.name}")

        if len(kept_photos) <= 3:
            # Few photos: send individually (no montage)
            _enrich_few_photos(event, kept_photos, provider, context)
            analyzed += 1
        else:
            # Build montage and analyze
            try:
                montage_data, photo_map = build_montage(kept_photos)
                if not montage_data:
                    _select_highlights(kept_photos)
                    analyzed += 1
                    continue

                result = provider.analyze_montage(
                    image_data=montage_data,
                    media_type="image/jpeg",
                    purpose="montage",
                    context=context,
                    image_count=len(photo_map),
                )
                event.summary = result.get("summary", "")
                event.description = event.summary

                # Mark highlights from Gemini's picks
                highlight_nums = result.get("highlights", [])
                if highlight_nums:
                    for num in highlight_nums:
                        if num in photo_map:
                            photo_map[num].is_highlight = True
                else:
                    _select_highlights(kept_photos)

                analyzed += 1

            except QuotaExhaustedError:
                quota_exhausted = True
                _select_highlights(kept_photos)
            except Exception:
                _select_highlights(kept_photos)
                analyzed += 1

        _progress("analyzing", analyzed, event_count,
                  f"[{event_idx}/{event_count}] {event.name}")

    # --- Thorough mode: Pass 2 & 3 ---
    if mode == "thorough" and not quota_exhausted:
        _enrich_thorough_pass(all_events, provider, _progress, event_count)

    _progress("done", event_count, event_count, "Enrichment complete")
    return trip


def _enrich_few_photos(event, photos, provider, context):
    """Enrich events with <=3 photos by sending individually."""
    descriptions = []
    for photo in photos:
        try:
            image_data, media_type = _read_image(photo.path)
            result = provider.analyze(image_data, media_type, "scene", context=context)
            photo.ai_description = result.description
            if result.description:
                descriptions.append(result.description)
        except Exception:
            pass

    if descriptions:
        event.summary = descriptions[0]
        event.description = descriptions[0]

    # All photos are highlights when <=3
    for p in photos:
        p.is_highlight = True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_enrich_montage.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -v`
Expected: All PASS (fix any existing tests that pass "full" or "reduced" as mode -- update to "quick"/"thorough")

- [ ] **Step 6: Commit**

```bash
git add src/post_trip_summary/pipeline/enrich.py tests/test_enrich_montage.py
git commit -m "Rewrite enrichment with montage-based quick mode"
```

---

### Task 6: Implement Thorough Mode (Pass 2 & 3)

**Files:**
- Modify: `src/post_trip_summary/pipeline/enrich.py`
- Modify: `tests/test_enrich_montage.py`

- [ ] **Step 1: Write failing test for thorough mode**

Add to `tests/test_enrich_montage.py`:

```python
class TestThoroughMode:
    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_thorough_sends_individual_photos_after_montage(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless

        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {
            "summary": "Toured the set.",
            "highlights": [1, 3, 5],
        }
        mock_provider.analyze.return_value = MagicMock(
            description="A hobbit hole.", landmark=None, confidence="medium"
        )
        mock_provider.synthesize.return_value = '{"narrative": "We walked through the magical Hobbiton set."}'
        mock_create.return_value = mock_provider

        trip = _trip_with_event(tmp_path, photo_count=10)
        result = enrich_trip_headless(trip, mode="thorough")

        event = result.days[0].events[0]
        assert event.summary == "Toured the set."
        # Narrative should differ from summary
        assert event.description != event.summary or "magical" in event.description
        # Individual analyze should have been called for highlights
        assert mock_provider.analyze.call_count >= 1

    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_thorough_calls_synthesize(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless

        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {
            "summary": "Toured the set.",
            "highlights": [1, 3],
        }
        mock_provider.analyze.return_value = MagicMock(
            description="A detailed scene.", landmark=None, confidence="medium"
        )
        mock_provider.synthesize.return_value = '{"narrative": "A rich journal narrative."}'
        mock_create.return_value = mock_provider

        trip = _trip_with_event(tmp_path, photo_count=8)
        result = enrich_trip_headless(trip, mode="thorough")

        mock_provider.synthesize.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_enrich_montage.py::TestThoroughMode -v`
Expected: FAIL -- `_enrich_thorough_pass` not defined or not producing narratives

- [ ] **Step 3: Implement `_enrich_thorough_pass`**

Add to `src/post_trip_summary/pipeline/enrich.py`:

```python
def _enrich_thorough_pass(all_events, provider, progress_fn, event_count):
    """Pass 2 (individual highlights) + Pass 3 (narrative synthesis) for thorough mode."""
    import json
    from post_trip_summary.vision.gemini import QuotaExhaustedError
    from post_trip_summary.vision.prompts import build_context, get_prompt

    quota_exhausted = False

    # Pass 2: Individual highlight descriptions
    for event_idx, event in enumerate(all_events, 1):
        if quota_exhausted:
            break

        highlights = [p for p in event.photos if p.is_highlight and p.is_kept]
        if not highlights:
            continue

        loc = event.location
        context = build_context(
            timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
            city=loc.city if loc else "",
            country=loc.country if loc else "",
            poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
        )

        progress_fn("detail", event_idx, event_count, f"Details: {event.name}")

        for photo in highlights:
            if quota_exhausted:
                break
            try:
                image_data, media_type = _read_image(photo.path)
                result = provider.analyze(image_data, media_type, "scene", context=context)
                photo.ai_description = result.description
            except QuotaExhaustedError:
                quota_exhausted = True
            except Exception:
                pass

    if quota_exhausted:
        return

    # Pass 3: Narrative synthesis
    synth_count = 0
    for event in all_events:
        described = [p for p in event.photos if p.is_highlight and p.ai_description]
        if len(described) < 2 or not event.summary:
            continue

        desc_lines = [f"{i + 1}. {p.ai_description}" for i, p in enumerate(described)]
        descriptions_text = "\n".join(desc_lines)

        loc = event.location
        context = build_context(
            timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
            city=loc.city if loc else "",
            country=loc.country if loc else "",
            poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
        )

        prompt = get_prompt(
            "narrative",
            context=context,
            montage_summary=event.summary,
            descriptions=descriptions_text,
        )
        try:
            raw = provider.synthesize(prompt)
            try:
                data = json.loads(raw)
                narrative = data.get("narrative", raw)
            except (json.JSONDecodeError, AttributeError):
                narrative = raw
            if narrative:
                event.description = narrative
                synth_count += 1
        except Exception:
            pass  # Keep the montage summary as description

    if synth_count:
        progress_fn("synthesizing", synth_count, synth_count,
                     f"Synthesized {synth_count} narratives")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_enrich_montage.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/post_trip_summary/pipeline/enrich.py tests/test_enrich_montage.py
git commit -m "Add thorough mode with individual highlights and narrative synthesis"
```

---

### Task 7: Update Cost Gate UI and Server Endpoints

**Files:**
- Modify: `src/post_trip_summary/templates/enrich.html:64-77`
- Modify: `src/post_trip_summary/server/app.py:213-230`

- [ ] **Step 1: Update enrich.html buttons**

In `src/post_trip_summary/templates/enrich.html`, replace the existing button group (around line 74-77):

Old:
```html
        <button class="btn-approve" id="btn-approve" onclick="startEnrich('full')">Approve</button>
        <button class="btn-reduce" id="btn-reduce" onclick="startEnrich('reduced')">Reduce Scope</button>
        <button class="btn-skip" id="btn-skip" onclick="startEnrich('skip')">Skip</button>
```

New:
```html
        <button class="btn-approve" id="btn-approve" onclick="startEnrich('quick')">Quick</button>
        <button class="btn-reduce" id="btn-reduce" onclick="startEnrich('thorough')">Thorough</button>
        <button class="btn-skip" id="btn-skip" onclick="startEnrich('skip')">Skip</button>
```

Also update the cost detail labels (around line 65-66):

Old:
```html
        <span class="label">Images (reduced)</span>
        <span class="value" id="est-reduced">--</span>
```

New:
```html
        <span class="label">Thorough mode (est.)</span>
        <span class="value" id="est-reduced">--</span>
```

- [ ] **Step 2: Update cost estimate API in app.py**

In `src/post_trip_summary/server/app.py`, update the `/api/enrich/estimate` endpoint to provide montage-based estimates. Replace the existing endpoint body:

```python
    @app.get("/api/enrich/estimate")
    def enrich_estimate():
        if app.state.trip is None:
            raise HTTPException(404, "No trip loaded")
        vs = get_vision_settings()
        all_events = [e for d in app.state.trip.days for e in d.events if e.photos]
        events_with_photos = [e for e in all_events if any(p.is_kept for p in e.photos)]

        montage_events = [e for e in events_with_photos if sum(1 for p in e.photos if p.is_kept) > 3]
        few_photo_events = [e for e in events_with_photos if sum(1 for p in e.photos if p.is_kept) <= 3]

        few_photo_calls = sum(min(3, sum(1 for p in e.photos if p.is_kept)) for e in few_photo_events)
        quick_calls = len(montage_events) + few_photo_calls
        thorough_extra = len(montage_events) * 5 + len(montage_events)  # highlights + synthesis
        thorough_calls = quick_calls + thorough_extra

        estimated_cost = 0.0
        if vs.get("api_key"):
            try:
                from post_trip_summary.vision.client import create_provider as _create_provider
                provider = _create_provider(vs["provider"], api_key=vs["api_key"], model=vs.get("model"))
                estimated_cost = provider.estimate_cost(thorough_calls)
            except Exception:
                pass

        return {
            "provider": vs["provider"],
            "model": vs.get("model", ""),
            "event_count": len(events_with_photos),
            "total_images": quick_calls,
            "reduced_images": thorough_calls,
            "estimated_cost": estimated_cost,
        }
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/post_trip_summary/templates/enrich.html src/post_trip_summary/server/app.py
git commit -m "Update cost gate UI and endpoints for quick/thorough modes"
```

---

### Task 8: Update CLI Enrichment Mode

**Files:**
- Modify: `src/post_trip_summary/cli.py`

- [ ] **Step 1: Find and update CLI enrichment code**

Search for the CLI enrich command and update mode options. In `src/post_trip_summary/cli.py`, find the enrichment prompt (the `enrich_trip` function or equivalent). Update the choice prompt:

Old pattern:
```python
        choice = click.prompt(
            "\n[a]pprove / [r]educe scope / [s]kip enrichment",
            type=str, default="a",
        )
```

New:
```python
        choice = click.prompt(
            "\n[q]uick / [t]horough / [s]kip enrichment",
            type=str, default="q",
        ).lower().strip()

        if choice in ("s", "skip"):
            # ... existing skip logic
        elif choice in ("t", "thorough"):
            # Run thorough enrichment
            pass
        else:
            # Run quick enrichment (default)
            pass
```

The exact changes depend on the current CLI structure. Read the file, locate the enrichment section, and update accordingly.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/post_trip_summary/cli.py
git commit -m "Update CLI enrichment to use quick/thorough modes"
```

---

### Task 9: Integration Test -- End-to-End Enrichment Modes

**Files:**
- Modify: `tests/test_wizard_integration.py`

- [ ] **Step 1: Add integration test for new mode values**

Add to `tests/test_wizard_integration.py`:

```python
def test_enrich_quick_mode_passes_through(client_with_trip):
    """Verify quick mode is passed through to enrichment pipeline."""
    client = client_with_trip
    with patch("post_trip_summary.server.compute.run_enrich_pipeline") as mock_run:
        mock_run.return_value = client.app.state.trip
        resp = client.post("/api/stage/start", json={"stage": "enrich", "mode": "quick"})
        assert resp.status_code == 200
        # Verify mode was passed
        args = mock_run.call_args
        assert args[0][1] == "quick" or args.kwargs.get("mode") == "quick"
```

Note: If the existing test fixture name differs, adapt accordingly. Check the file for the correct fixture pattern before adding.

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/test_wizard_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_wizard_integration.py
git commit -m "Add integration test for montage enrichment modes"
```

---

### Task 10: Clean Up -- Remove Dead Code and Update Docs

**Files:**
- Modify: `src/post_trip_summary/vision/triage.py` (if `plan_enrichment` is unused)
- Modify: `src/post_trip_summary/pipeline/enrich.py` (remove old `enrich_trip` CLI function if superseded)
- Modify: `CLAUDE.md`

- [ ] **Step 1: Check for dead code**

```bash
grep -rn "plan_enrichment" src/ tests/
grep -rn "enrich_trip[^_]" src/ tests/
```

If `plan_enrichment` is only called from old enrichment code that has been replaced, remove or simplify `triage.py`. Keep `select_representatives`, `_deduplicate_by_hash`, and `estimate_batch_cost` if they're still referenced.

If `enrich_trip` (the CLI-interactive version) is still called from `cli.py`, update it to use the new mode names. If it's been fully replaced by `enrich_trip_headless`, remove it.

- [ ] **Step 2: Update CLAUDE.md architecture section**

Replace the Enrich stage description:

Old:
```markdown
4. **Enrich** — Vision API (Gemini or Claude) describes highlight photos
```

New:
```markdown
4. **Enrich** — Montage-based vision analysis (Gemini). Quick mode: one montage per event for factual summaries. Thorough mode: montages + individual highlight descriptions + journal-style narratives.
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "Clean up dead enrichment code and update docs"
```
