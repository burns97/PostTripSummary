from pathlib import Path

from fastapi.testclient import TestClient

from post_trip_summary.config import create_session


def test_create_app_returns_fastapi(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    assert app is not None
    client = TestClient(app)
    response = client.get("/api/stage/current")
    assert response.status_code == 200
    assert response.json()["stage"] == "new"


def test_app_state_holds_session(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    assert app.state.session.slug == "test-trip"
    assert app.state.trip is None


def test_wizard_root_redirects_to_current_step(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert "/wizard/setup" in response.headers["location"]


def test_wizard_setup_page_renders(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.get("/wizard/setup")
    assert response.status_code == 200
    assert "Setup" in response.text
    assert "test-trip" in response.text


def test_update_inputs_saves_to_session(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    response = client.post("/api/session/inputs", json={
        "inputs": {"photos": str(photos_dir)},
        "settings": {},
    })
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert app.state.session.inputs["photos"] == str(photos_dir)
    assert app.state.session.current_stage == "setup"


def test_update_inputs_validates_photos_path(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.post("/api/session/inputs", json={
        "inputs": {"photos": "/nonexistent/path"},
        "settings": {},
    })
    assert response.status_code == 422


def test_update_inputs_optional_sources_not_validated_if_empty(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    response = client.post("/api/session/inputs", json={
        "inputs": {"photos": str(photos_dir)},
        "settings": {"vision_provider": "gemini"},
    })
    assert response.status_code == 200
