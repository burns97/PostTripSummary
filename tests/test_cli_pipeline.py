# tests/test_cli_pipeline.py
from datetime import date, datetime
from unittest.mock import patch

from click.testing import CliRunner
from post_trip_summary.cli import cli
from post_trip_summary.config import create_session, load_session
from post_trip_summary.models import Day, Event, Location, Photo, Trip
from post_trip_summary.serialization import save_trip


def test_start_unknown_session(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["start", "nonexistent", "--base-dir", str(tmp_path)])
    assert result.exit_code != 0


def test_generate_no_data(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["new", "Test Trip", "--base-dir", str(tmp_path)])
    result = runner.invoke(cli, ["generate", "test-trip", "--base-dir", str(tmp_path)])
    assert result.exit_code != 0 or "No data" in result.output or "no final" in result.output.lower()


def _final_trip(tmp_path) -> Trip:
    photo_path = tmp_path / "photo.jpg"
    photo_path.write_bytes(b"not-used-by-patched-generators")
    photo = Photo(
        path=photo_path,
        timestamp=datetime(2026, 3, 5, 10, 0),
        gps=(48.858, 2.294),
        is_highlight=True,
        is_kept=True,
    )
    event = Event(
        id="day01-event01",
        type="landmark",
        name="Eiffel Tower",
        time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 11, 0)),
        location=Location(
            lat=48.858,
            lon=2.294,
            name="Eiffel Tower",
            address=None,
            city="Paris",
            country="France",
        ),
        photos=[photo],
        description="A visit to the Eiffel Tower.",
    )
    return Trip(
        name="Paris 2026",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )


def test_generate_command_creates_trip_story(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    save_trip(_final_trip(tmp_path), session.stage_file("final"))

    with patch("post_trip_summary.cli._generate_static_map", return_value=None), \
         patch("post_trip_summary.output.photo_prep.prepare_photos"), \
         patch("post_trip_summary.output.detailed_record.generate_detailed_record"), \
         patch("post_trip_summary.output.shareable_pdf.generate_shareable_pdf"), \
         patch("post_trip_summary.output.blog_post.generate_blog_post"), \
         patch("post_trip_summary.output.trip_story.generate_trip_story") as story:
        result = runner.invoke(cli, ["generate", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    story.assert_called_once()
    assert "Generating trip story" in result.output


def test_preview_accepts_highlights_done_stage(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    save_trip(_final_trip(tmp_path), session.stage_file("highlights_done"))

    with patch("post_trip_summary.preview.server.run_preview") as run_preview:
        result = runner.invoke(cli, ["preview", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    run_preview.assert_called_once()


def test_preview_uses_enriched_data_when_stale_final_file_exists(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    current_trip = _final_trip(tmp_path)
    current_trip.name = "Current enriched"
    stale_trip = _final_trip(tmp_path)
    stale_trip.name = "Stale final"
    save_trip(current_trip, session.stage_file("enriched"))
    save_trip(stale_trip, session.stage_file("highlights_done"))

    with patch("post_trip_summary.preview.server.run_preview") as run_preview:
        result = runner.invoke(cli, ["preview", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert run_preview.call_args.args[0].name == "Current enriched"


def test_generate_reports_current_highlights_stage_when_missing_data(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()

    result = runner.invoke(cli, ["generate", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "No highlights_done data" in result.output


def test_review_skeleton_accepts_ingested_stage(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()
    save_trip(_final_trip(tmp_path), session.stage_file("ingested"))

    with patch("post_trip_summary.preview.server.run_preview") as run_preview:
        result = runner.invoke(cli, ["review-skeleton", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    run_preview.assert_called_once()


def test_review_skeleton_rejects_legacy_raw_ingest_stage(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "ingest"
    session.save()

    result = runner.invoke(cli, ["review-skeleton", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "Review-skeleton requires ingested, reviewed stage" in result.output


def test_cull_photos_accepts_reviewed_stage(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    save_trip(_final_trip(tmp_path), session.stage_file("reviewed"))

    with patch("post_trip_summary.preview.server.run_preview") as run_preview:
        result = runner.invoke(cli, ["cull-photos", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    run_preview.assert_called_once()


def test_pick_highlights_accepts_highlights_done_stage(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "highlights_done"
    session.save()
    save_trip(_final_trip(tmp_path), session.stage_file("highlights_done"))

    with patch("post_trip_summary.preview.server.run_preview") as run_preview:
        result = runner.invoke(cli, ["pick-highlights", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    run_preview.assert_called_once()


def test_pick_highlights_uses_enriched_data_when_stale_final_file_exists(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    current_trip = _final_trip(tmp_path)
    current_trip.name = "Current enriched"
    stale_trip = _final_trip(tmp_path)
    stale_trip.name = "Stale final"
    save_trip(current_trip, session.stage_file("enriched"))
    save_trip(stale_trip, session.stage_file("highlights_done"))

    with patch("post_trip_summary.preview.server.run_preview") as run_preview:
        result = runner.invoke(cli, ["pick-highlights", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert run_preview.call_args.args[0].name == "Current enriched"


def test_discover_command_creates_vacation_blend(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    save_trip(_final_trip(tmp_path), session.stage_file("reviewed"))

    result = runner.invoke(cli, ["discover", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "Vacation Blend" in result.output
    assert "Analysis mode: metadata_only" in result.output
    assert "Primary themes:" in result.output
    assert "Saved artifact:" in result.output
    assert "Debug report:" in result.output
    assert (session.session_dir / "vacation_blend.json").exists()
    assert (session.session_dir / "vacation_blend_debug.md").exists()
    assert load_session("paris-2026", base_dir=tmp_path).current_stage == "discovered"


def test_discover_command_requires_reviewed_data(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()

    result = runner.invoke(cli, ["discover", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "No reviewed trip data" in result.output


def test_discover_command_reports_missing_session(tmp_path):
    runner = CliRunner()

    result = runner.invoke(cli, ["discover", "missing-trip", "--base-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "Session 'missing-trip' not found" in result.output


def test_local_prefill_updates_reviewed_trip(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "reviewed"
    session.save()
    trip = _final_trip(tmp_path)
    trip.days[0].events[0].photos[0].ai_description = None
    save_trip(trip, session.stage_file("reviewed"))

    class Stats:
        events_seen = 1
        photos_attempted = 1
        photos_described = 1
        skipped_existing = 0
        failed = 0
        summaries_written = 1

    def fake_prefill(loaded_trip, **kwargs):
        loaded_trip.days[0].events[0].photos[0].ai_description = "Local draft."
        return Stats()

    with patch("post_trip_summary.pipeline.local_prefill.prefill_trip_with_local_descriptions", side_effect=fake_prefill):
        result = runner.invoke(cli, ["local-prefill", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "Local prefill complete" in result.output
    from post_trip_summary.serialization import load_trip
    saved = load_trip(session.stage_file("reviewed"))
    assert saved.days[0].events[0].photos[0].ai_description == "Local draft."
    assert load_session("paris-2026", base_dir=tmp_path).current_stage == "reviewed"


def test_local_prefill_updates_enriched_trip(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "enriched"
    session.save()
    trip = _final_trip(tmp_path)
    trip.days[0].events[0].photos[0].ai_description = None
    save_trip(trip, session.stage_file("enriched"))

    class Stats:
        events_seen = 1
        photos_attempted = 1
        photos_described = 1
        skipped_existing = 0
        failed = 0
        summaries_written = 1

    def fake_prefill(loaded_trip, **kwargs):
        loaded_trip.days[0].events[0].photos[0].ai_description = "Enriched local draft."
        return Stats()

    with patch("post_trip_summary.pipeline.local_prefill.prefill_trip_with_local_descriptions", side_effect=fake_prefill):
        result = runner.invoke(cli, ["local-prefill", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    from post_trip_summary.serialization import load_trip
    saved = load_trip(session.stage_file("enriched"))
    assert saved.days[0].events[0].photos[0].ai_description == "Enriched local draft."


def test_local_prefill_discovered_stage_invalidates_discovery(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "discovered"
    session.save()
    trip = _final_trip(tmp_path)
    save_trip(trip, session.stage_file("reviewed"))
    artifact = session.session_dir / "vacation_blend.json"
    debug = session.session_dir / "vacation_blend_debug.md"
    artifact.write_text("{}", encoding="utf-8")
    debug.write_text("# stale", encoding="utf-8")

    class Stats:
        events_seen = 1
        photos_attempted = 1
        photos_described = 1
        skipped_existing = 0
        failed = 0
        summaries_written = 1

    with patch("post_trip_summary.pipeline.local_prefill.prefill_trip_with_local_descriptions", return_value=Stats()):
        result = runner.invoke(cli, ["local-prefill", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code == 0
    loaded = load_session("paris-2026", base_dir=tmp_path)
    assert loaded.current_stage == "reviewed"
    assert not artifact.exists()
    assert not debug.exists()


def test_local_prefill_rejects_missing_reviewed_or_enriched_data(tmp_path):
    runner = CliRunner()
    session = create_session("Paris 2026", base_dir=tmp_path)
    session.current_stage = "ingested"
    session.save()

    result = runner.invoke(cli, ["local-prefill", "paris-2026", "--base-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "Local prefill requires reviewed, discovered, or enriched stage" in result.output
