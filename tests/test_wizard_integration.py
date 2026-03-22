"""Integration test: create session via CLI, launch wizard, configure inputs."""
import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from PIL import Image

from post_trip_summary.cli import cli
from post_trip_summary.config import create_session, load_session


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
