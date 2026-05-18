from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from post_trip_summary.config import create_session
from post_trip_summary.models import Day, Event, Location, Photo, Trip


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


def test_photo_serving_by_event_and_index(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)

    client = TestClient(app)
    response = client.get("/photos/day01-event01/0")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_photo_serving_by_filename(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)

    client = TestClient(app)
    response = client.get("/photos/photo.jpg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_photo_serving_not_found(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)

    client = TestClient(app)
    response = client.get("/photos/nonexistent-event/0")
    assert response.status_code == 404


def test_start_ingest_returns_ok(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    session.inputs["photos"] = str(photos_dir)
    session.current_stage = "setup"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.post("/api/stage/start", json={"stage": "ingest"})
    assert response.status_code == 200
    assert response.json()["status"] == "started"


def test_ingest_page_renders(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "setup"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.get("/wizard/ingest")
    assert response.status_code == 200
    assert "Processing" in response.text or "progress" in response.text.lower()


def test_progress_endpoint_exists(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    client = TestClient(app)
    response = client.get("/api/progress")
    assert response.status_code == 200


def test_toggle_keep(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/toggle-keep", json={"event_id": "day01-event01", "photo_index": 0})
    assert response.status_code == 200
    assert response.json()["is_kept"] is False


def test_skeleton_rename(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/skeleton/rename", json={"event_id": "day01-event01", "new_name": "Renamed"})
    assert response.status_code == 200
    assert response.json()["new_name"] == "Renamed"


def test_review_page_renders_with_trip(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/wizard/review")
    assert response.status_code == 200
    assert "day01-event01" in response.text


def test_advance_stage(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/stage/advance")
    assert response.status_code == 200
    assert response.json()["stage"] == "reviewed"


def test_advance_stage_from_reviewed_returns_discovered_and_enrich_next_step(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)

    response = client.post("/api/stage/advance")

    assert response.status_code == 200
    assert response.json() == {"stage": "discovered", "next_step": "enrich"}


def test_enrich_estimate_endpoint(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    from post_trip_summary.server.app import create_app, _build_event_index
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/api/enrich/estimate")
    assert response.status_code == 200
    data = response.json()
    assert "total_images" in data
    assert "estimated_cost" in data
    assert "provider" in data
    assert "has_api_key" in data
    assert "event_count" in data


def test_enrich_page_renders(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    from post_trip_summary.server.app import create_app, _build_event_index
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/wizard/enrich")
    assert response.status_code == 200
    assert "Enrichment" in response.text or "enrich" in response.text.lower()


def test_enrich_page_renders_for_discovered_session(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "discovered"
    session.save()
    from post_trip_summary.server.app import create_app, _build_event_index
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)

    response = client.get("/wizard/enrich", follow_redirects=False)

    assert response.status_code == 200
    assert "Enrichment" in response.text or "enrich" in response.text.lower()


def test_toggle_highlight(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/toggle-highlight", json={"event_id": "day01-event01", "photo_index": 0})
    assert response.status_code == 200
    assert response.json()["is_highlight"] is True  # was False, now toggled


def test_toggle_highlight_invalid_event(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/toggle-highlight", json={"event_id": "nonexistent", "photo_index": 0})
    assert response.status_code == 404


def test_bulk_action_highlight_all(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/bulk-action", json={"event_id": "day01-event01", "action": "highlight_all"})
    assert response.status_code == 200
    assert response.json()["action"] == "highlight_all"
    # Photo is kept by default, so it should now be highlighted
    event = app.state.event_index["day01-event01"]
    assert event.photos[0].is_highlight is True


def test_bulk_action_highlight_none(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    # First highlight, then clear
    event = app.state.event_index["day01-event01"]
    event.photos[0].is_highlight = True
    client = TestClient(app)
    response = client.post("/api/bulk-action", json={"event_id": "day01-event01", "action": "highlight_none"})
    assert response.status_code == 200
    assert event.photos[0].is_highlight is False


def test_highlights_page_renders(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/wizard/highlights")
    assert response.status_code == 200
    assert "day01-event01" in response.text


def test_generate_page_renders(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/wizard/generate")
    assert response.status_code == 200
    assert "Generate" in response.text


def test_generate_api(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/generate", json={
        "detailed_record": True,
        "shareable_pdf": False,
        "blog_post": False,
        "photo_prep": False,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert any(f["type"] == "detailed_record" for f in data["files"])
    assert session.current_stage == "generated"


def test_generate_api_blog_post(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.post("/api/generate", json={
        "detailed_record": False,
        "shareable_pdf": False,
        "blog_post": True,
        "photo_prep": False,
    })
    assert response.status_code == 200
    data = response.json()
    assert any(f["type"] == "blog_post" for f in data["files"])


def test_generate_api_no_trip(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    # trip is None
    client = TestClient(app)
    response = client.post("/api/generate", json={"detailed_record": True})
    assert response.status_code == 400


def test_preview_detailed_endpoint(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/detailed")
    assert response.status_code == 200
    assert "Test" in response.text


def test_preview_summary_endpoint(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/summary")
    assert response.status_code == 200


def test_preview_blog_endpoint(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    from post_trip_summary.server.app import create_app
    app = create_app(session)
    app.state.trip = _make_test_trip(tmp_path)
    from post_trip_summary.server.app import _build_event_index
    app.state.event_index = _build_event_index(app.state.trip)
    client = TestClient(app)
    response = client.get("/blog")
    assert response.status_code == 200


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
