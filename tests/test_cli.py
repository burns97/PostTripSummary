# tests/test_cli.py
from click.testing import CliRunner
from post_trip_summary.cli import cli


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
