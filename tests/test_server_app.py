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
