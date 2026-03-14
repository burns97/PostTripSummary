# src/post_trip_summary/cli.py
"""CLI entry point for Post-Trip Summary."""
import click
from pathlib import Path

from post_trip_summary.config import (
    create_session, load_session, list_sessions, delete_session, DEFAULT_BASE_DIR,
)


@click.group()
@click.version_option()
def cli():
    """Post-Trip Summary — Generate trip summaries from vacation photos and travel data."""
    pass


@cli.command()
@click.argument("name")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def new(name: str, base_dir: Path | None):
    """Create a new trip session."""
    base = base_dir or DEFAULT_BASE_DIR
    session = create_session(name, base_dir=base)
    click.echo(f"Created session '{session.name}' ({session.slug})")
    photos_path = click.prompt("Where are your photos?", type=str)
    session.inputs["photos"] = photos_path
    session.save()
    click.echo(f"Session saved. Run 'post-trip-summary resume {session.slug}' to continue.")


@cli.command("list")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def list_cmd(base_dir: Path | None):
    """List all trip sessions."""
    base = base_dir or DEFAULT_BASE_DIR
    sessions = list_sessions(base_dir=base)
    if not sessions:
        click.echo("No sessions found.")
        return
    for s in sessions:
        click.echo(f"  {s.slug}  ({s.name})  stage: {s.current_stage}")


@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def delete(slug: str, base_dir: Path | None):
    """Delete a trip session."""
    base = base_dir or DEFAULT_BASE_DIR
    if click.confirm(f"Delete session '{slug}'? This cannot be undone"):
        delete_session(slug, base_dir=base)
        click.echo(f"Deleted session '{slug}'.")


@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def resume(slug: str, base_dir: Path | None):
    """Resume a trip session from where you left off."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    click.echo(f"Resuming '{session.name}' at stage: {session.current_stage}")
    # STUB: Pipeline stages will be wired in Chunk 6, Task 24. This is intentionally incomplete.


@cli.command("add-input")
@click.argument("slug")
@click.option("--photos", type=click.Path(exists=True, path_type=Path))
@click.option("--excel", type=click.Path(exists=True, path_type=Path))
@click.option("--credit-card", type=click.Path(exists=True, path_type=Path))
@click.option("--google-maps", type=click.Path(exists=True, path_type=Path))
@click.option("--apple-health", type=click.Path(exists=True, path_type=Path))
@click.option("--dayone", type=click.Path(exists=True, path_type=Path))
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def add_input(slug: str, base_dir: Path | None, **inputs):
    """Add input data sources to a session."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    for key, value in inputs.items():
        if key == "base_dir":
            continue
        if value is not None:
            session.inputs[key.replace("-", "_")] = str(value)
            click.echo(f"  Added {key}: {value}")
    session.save()
