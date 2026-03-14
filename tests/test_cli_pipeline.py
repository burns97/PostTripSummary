# tests/test_cli_pipeline.py
from click.testing import CliRunner
from post_trip_summary.cli import cli


def test_resume_unknown_session(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["resume", "nonexistent", "--base-dir", str(tmp_path)])
    assert result.exit_code != 0 or "not found" in result.output.lower() or "Error" in result.output


def test_generate_no_data(tmp_path):
    runner = CliRunner()
    runner.invoke(cli, ["new", "Test Trip", "--base-dir", str(tmp_path)], input="/fake/path\n")
    result = runner.invoke(cli, ["generate", "test-trip", "--base-dir", str(tmp_path)])
    assert result.exit_code != 0 or "No data" in result.output or "no final" in result.output.lower()
