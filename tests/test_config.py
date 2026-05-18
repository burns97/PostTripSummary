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
    session.current_stage = "ingested"
    session.save()
    loaded = load_session("paris-2026", base_dir=tmp_path)
    assert loaded.current_stage == "ingested"


def test_config_settings_defaults(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    assert session.settings["cluster_time_gap_minutes"] == 15
    assert session.settings["cluster_distance_meters"] == 200


def test_new_stages_list():
    from post_trip_summary.config import STAGES
    assert STAGES == ["new", "setup", "ingested", "reviewed", "discovered", "enriched", "highlights_done", "generated"]


def test_stage_file_ingested(tmp_path):
    session = create_session("test", base_dir=tmp_path)
    assert session.stage_file("ingested").name == "trip_ingested.json"


def test_stage_file_reviewed(tmp_path):
    session = create_session("test", base_dir=tmp_path)
    assert session.stage_file("reviewed").name == "trip_reviewed.json"


def test_stage_file_highlights_done(tmp_path):
    session = create_session("test", base_dir=tmp_path)
    assert session.stage_file("highlights_done").name == "trip_final.json"
