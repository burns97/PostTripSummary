# tests/test_cli.py
from datetime import date, datetime

from click.testing import CliRunner

from post_trip_summary.cli import cli
from post_trip_summary.config import create_session
from post_trip_summary.models import Day, Event, Location, Trip
from post_trip_summary.serialization import save_trip


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Post-Trip Summary" in result.output


def test_new_command(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["new", "Paris 2026", "--base-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "paris-2026" in result.output


def test_list_command_empty(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["list", "--base-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "No sessions" in result.output


def test_list_command_with_sessions(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["new", "Paris 2026", "--base-dir", str(tmp_path)])
    result = runner.invoke(cli, ["list", "--base-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "paris-2026" in result.output


def test_delete_command(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["new", "Paris 2026", "--base-dir", str(tmp_path)])
    result = runner.invoke(cli, ["delete", "paris-2026", "--base-dir", str(tmp_path)], input="y\n")
    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_start_command_exists():
    from click.testing import CliRunner
    from post_trip_summary.cli import cli
    runner = CliRunner()
    result = runner.invoke(cli, ["start", "--help"])
    assert result.exit_code == 0
    assert "Launch the browser wizard" in result.output


def test_geocode_audit_reports_airport_candidate(tmp_path):
    session = create_session("New Zealand 2026", base_dir=tmp_path)
    trip = Trip(
        name="New Zealand 2026",
        date_range=(date(2026, 2, 18), date(2026, 2, 18)),
        days=[
            Day(
                date=date(2026, 2, 18),
                events=[
                    Event(
                        id="day01-event01",
                        type="unknown",
                        name="Ticketing Level",
                        time_range=(
                            datetime(2026, 2, 18, 15, 25, 21),
                            datetime(2026, 2, 18, 15, 25, 21),
                        ),
                        location=Location(
                            lat=39.99786388888889,
                            lon=-82.88245277777777,
                            name="Ticketing Level",
                            address=None,
                            city="Columbus",
                            country="US",
                        ),
                        geo_context={
                            "is_airport": True,
                            "poi_name": "Ticketing Level",
                            "area_name": "Columbus",
                        },
                        name_candidates={
                            "Airport": "Ticketing Level",
                            "Area": "Columbus",
                        },
                    )
                ],
            )
        ],
    )
    save_trip(trip, session.stage_file("ingested"))

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["geocode-audit", session.slug, "--base-dir", str(tmp_path), "--only-airports"],
    )

    assert result.exit_code == 0
    assert "day01-event01" in result.output
    assert "Ticketing Level" in result.output
    assert "John Glenn Columbus International Airport (CMH)" in result.output
