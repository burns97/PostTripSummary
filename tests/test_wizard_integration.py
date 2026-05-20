"""Integration test: create session via CLI, launch wizard, configure inputs."""
import asyncio
import time
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from PIL import Image

from post_trip_summary.cli import cli
from post_trip_summary.config import create_session, load_session
from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.serialization import save_vacation_blend, vacation_blend_path
from post_trip_summary.models import Day, Event, Location, Photo, Trip


def test_new_then_start_setup_flow(tmp_path):
    """Simulate: new -> start -> configure inputs on setup page."""
    runner = CliRunner()

    # 1. Create session
    result = runner.invoke(cli, ["new", "Test Trip", "--base-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "test-trip" in result.output

    # 2. Load session and create app (simulates what `start` does)
    session = load_session("test-trip", base_dir=tmp_path)
    assert session.current_stage == "new"

    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)

    # 3. Root redirects to setup
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert "/wizard/setup" in response.headers["location"]

    # 4. Setup page renders
    response = client.get("/wizard/setup")
    assert response.status_code == 200
    assert "Test Trip" in response.text

    # 5. Submit inputs
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()

    response = client.post("/api/session/inputs", json={
        "inputs": {"photos": str(photos_dir)},
        "settings": {"vision_provider": "gemini"},
    })
    assert response.status_code == 200

    # 6. Session updated
    assert session.current_stage == "setup"
    assert session.inputs["photos"] == str(photos_dir)

    # 7. Stage endpoint reflects current state
    response = client.get("/api/stage/current")
    assert response.json()["stage"] == "setup"


def _create_test_photos(directory, count=3):
    for i in range(count):
        img_path = directory / f"IMG_{i:04d}.jpg"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path, "JPEG")


@pytest.mark.anyio
async def test_setup_to_ingest_flow(tmp_path):
    """Simulate: setup inputs -> start ingest -> poll progress -> completion."""
    import httpx
    from post_trip_summary.server.app import create_app

    session = create_session("test-trip", base_dir=tmp_path)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    _create_test_photos(photos_dir, count=3)
    session.inputs["photos"] = str(photos_dir)
    session.current_stage = "setup"
    session.save()

    app = create_app(session)

    mock_geo = {"name": "Test Place", "city": "Paris", "country": "France",
                "address": "123 Test St", "lat": 48.858, "lon": 2.294}
    with patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/stage/start",
                json={"stage": "ingest"},
            )
            assert response.status_code == 200

            # Poll until done — asyncio.sleep yields to the event loop so
            # the background task can make progress.
            state = {}
            for _ in range(60):
                await asyncio.sleep(0.5)
                state = app.state.progress.get_state()
                if state["done"] or state["failed"]:
                    break

    assert state["done"] is True, f"Expected done, got: {state}"
    assert app.state.session.current_stage == "ingested"
    assert app.state.trip is not None


def _make_test_trip(tmp_path):
    """Create a minimal trip with one photo on disk."""
    img_path = tmp_path / "photo.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(img_path, "JPEG")

    photo = Photo(path=img_path, timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294))
    event = Event(
        id="day01-event01",
        type="landmark",
        name="Test",
        time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
        location=Location(lat=48.858, lon=2.294, name="Test", address=None, city="Paris", country="France"),
        photos=[photo],
    )
    return Trip(
        name="Test",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )


def _save_test_vacation_blend(session):
    save_vacation_blend(
        vacation_blend_path(session.session_dir),
        VacationBlend(
            analysis_mode="metadata",
            confidence="high",
            primary=[
                ThemeScore(
                    theme_id="culture_sightseeing",
                    label="Culture & sightseeing",
                    score=5.0,
                    evidence=[],
                    sample_event_ids=[],
                )
            ],
            secondary=[],
            rejected=[],
            diagnostics={},
            warnings=[],
        ),
    )


def test_review_flow(tmp_path):
    """Integration test: ingested stage -> review page -> edit -> advance to reviewed."""
    from post_trip_summary.server.app import create_app, _build_event_index

    # 1. Create session at "ingested" stage with a test trip loaded
    session = create_session("review-flow-trip", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()

    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)

    client = TestClient(app)

    # 2. Review page renders and contains event data
    response = client.get("/wizard/review")
    assert response.status_code == 200
    assert "day01-event01" in response.text

    # 3. Toggle a photo's kept status (photos start as kept=True by default)
    response = client.post("/api/toggle-keep", json={"event_id": "day01-event01", "photo_index": 0})
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == "day01-event01"
    assert data["photo_index"] == 0
    assert data["is_kept"] is False  # toggled from True to False

    # 4. Rename the event
    response = client.post("/api/skeleton/rename", json={"event_id": "day01-event01", "new_name": "Eiffel Tower"})
    assert response.status_code == 200
    data = response.json()
    assert data["new_name"] == "Eiffel Tower"
    # Confirm the in-memory event was updated
    assert app.state.trip.days[0].events[0].name == "Eiffel Tower"

    # 5. Advance the stage from "ingested" to "reviewed"
    response = client.post("/api/stage/advance")
    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "reviewed"

    # 6. Session is now at stage "reviewed"
    assert session.current_stage == "reviewed"


def test_enrich_estimate_returns_data(tmp_path):
    """Integration test: reviewed stage -> GET /api/enrich/estimate returns cost data."""
    from post_trip_summary.server.app import create_app, _build_event_index

    session = create_session("enrich-estimate-trip", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()

    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)

    client = TestClient(app)

    response = client.get("/api/enrich/estimate")
    assert response.status_code == 200
    data = response.json()
    assert "total_images" in data
    assert "estimated_cost" in data
    assert isinstance(data["total_images"], int)
    assert isinstance(data["estimated_cost"], float)


def test_highlights_flow(tmp_path):
    """Integration test: enriched stage -> highlights page -> toggle highlight -> advance."""
    from post_trip_summary.server.app import create_app, _build_event_index

    session = create_session("highlights-flow-trip", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()

    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)

    client = TestClient(app)

    # 1. Highlights page renders
    response = client.get("/wizard/highlights")
    assert response.status_code == 200

    # 2. Toggle highlight on the first photo of the first event
    response = client.post(
        "/api/toggle-highlight",
        json={"event_id": "day01-event01", "photo_index": 0},
    )
    assert response.status_code == 200
    data = response.json()
    assert "is_highlight" in data
    assert data["is_highlight"] is True  # starts False, toggled to True

    # 3. Advance stage from "enriched" to "highlights_done"
    response = client.post("/api/stage/advance")
    assert response.status_code == 200
    data = response.json()
    assert data["stage"] == "highlights_done"

    # 4. Session reflects the new stage
    assert session.current_stage == "highlights_done"


def test_enrich_quick_mode_passes_through(tmp_path):
    """Integration test: verify quick mode is passed through to enrichment pipeline."""
    from post_trip_summary.server.app import create_app, _build_event_index

    session = create_session("enrich-mode-trip", base_dir=tmp_path)
    session.current_stage = "discovered"
    _save_test_vacation_blend(session)
    session.save()

    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)

    client = TestClient(app)

    # Mock the run_enrich_pipeline function to verify it's called with mode="quick"
    with patch("post_trip_summary.server.compute.run_enrich_pipeline") as mock_run:
        mock_run.return_value = app.state.trip

        response = client.post("/api/stage/start", json={"stage": "enrich", "mode": "quick"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"

        # Verify the mock was called with the correct mode
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # run_enrich_pipeline(session, mode, progress_callback)
        assert call_args[0][1] == "quick"  # Second positional argument is mode
