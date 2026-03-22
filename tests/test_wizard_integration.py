"""Integration test: create session via CLI, launch wizard, configure inputs."""
from pathlib import Path
from click.testing import CliRunner
from fastapi.testclient import TestClient
from post_trip_summary.cli import cli
from post_trip_summary.config import load_session


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
