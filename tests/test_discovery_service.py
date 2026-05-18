import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from post_trip_summary.config import DEFAULT_SETTINGS, STAGES, create_session, load_session
from post_trip_summary.discovery.serialization import (
    load_vacation_blend,
    vacation_blend_path,
)
from post_trip_summary.discovery.service import run_discovery_for_session
from post_trip_summary.models import Day, Event, Location, Photo, Trip
from post_trip_summary.serialization import save_trip


def _reviewed_trip() -> Trip:
    start = datetime(2026, 1, 1, 9, 0)
    event = Event(
        id="event-1",
        type="activity",
        name="Historic museum gallery walk and cafe lunch",
        time_range=(start, start + timedelta(hours=2)),
        location=Location(
            lat=48.8566,
            lon=2.3522,
            name="Historic museum cafe",
            address="Paris",
            city="Paris",
            country="France",
        ),
        photos=[
            Photo(
                path=Path("photo-1.jpg"),
                timestamp=start + timedelta(minutes=10),
                gps=(48.8566, 2.3522),
            )
        ],
    )
    day = Day(date=date(2026, 1, 1), events=[event])
    return Trip(name="Paris 2026", date_range=(day.date, day.date), days=[day])


def test_discovered_stage_exists_immediately_after_reviewed():
    reviewed_index = STAGES.index("reviewed")
    assert STAGES[reviewed_index + 1] == "discovered"


def test_default_settings_include_discovery_defaults_when_creating_and_loading_session(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    loaded = load_session("paris-2026", base_dir=tmp_path)

    expected = {
        "mode": "metadata_only",
        "enable_local_ai": False,
        "local_provider_url": None,
        "local_model": None,
        "enable_cloud_synthesis": False,
        "max_local_images": 150,
        "max_cloud_images": 40,
        "timeout_seconds": 30,
    }
    assert DEFAULT_SETTINGS["discovery"] == expected
    assert session.settings["discovery"] == expected
    assert loaded.settings["discovery"] == expected


def test_nested_discovery_settings_merge_with_defaults(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    config_path = session.session_dir / "config.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    data["settings"] = {"discovery": {"enable_local_ai": True}}
    config_path.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_session("paris-2026", base_dir=tmp_path)

    assert loaded.settings["discovery"]["enable_local_ai"] is True
    assert loaded.settings["discovery"]["mode"] == "metadata_only"
    assert loaded.settings["discovery"]["enable_cloud_synthesis"] is False
    assert loaded.settings["discovery"]["max_local_images"] == 150
    assert loaded.settings["discovery"]["timeout_seconds"] == 30


def test_run_discovery_saves_artifact_returns_loaded_blend_and_advances_reviewed_session(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    save_trip(_reviewed_trip(), session.stage_file("reviewed"))

    blend = run_discovery_for_session(session)

    artifact_path = vacation_blend_path(session.session_dir)
    loaded_blend = load_vacation_blend(artifact_path)
    detected = {score.theme_id for score in blend.primary + blend.secondary}
    assert artifact_path.exists()
    assert loaded_blend == blend
    assert {"culture_sightseeing", "food_drink"} <= detected
    assert session.current_stage == "discovered"
    assert load_session("paris-2026", base_dir=tmp_path).current_stage == "discovered"


def test_run_discovery_with_advance_stage_false_leaves_reviewed_session(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    save_trip(_reviewed_trip(), session.stage_file("reviewed"))

    run_discovery_for_session(session, advance_stage=False)

    assert vacation_blend_path(session.session_dir).exists()
    assert session.current_stage == "reviewed"
    assert load_session("paris-2026", base_dir=tmp_path).current_stage == "reviewed"


def test_run_discovery_does_not_regress_later_stage(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    save_trip(_reviewed_trip(), session.stage_file("reviewed"))

    run_discovery_for_session(session)

    assert session.current_stage == "enriched"
    assert load_session("paris-2026", base_dir=tmp_path).current_stage == "enriched"


def test_run_discovery_missing_reviewed_trip_raises_file_not_found(tmp_path):
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()

    with pytest.raises(FileNotFoundError, match="Reviewed trip file not found"):
        run_discovery_for_session(session)
