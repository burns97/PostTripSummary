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
    """Post-Trip Summary - Generate trip summaries from vacation photos and travel data."""
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
    try:
        session = load_session(slug, base_dir=base)
    except FileNotFoundError:
        click.echo(f"Error: Session '{slug}' not found.")
        raise SystemExit(1)

    click.echo(f"Resuming '{session.name}' at stage: {session.current_stage}")

    from post_trip_summary.serialization import save_trip, load_trip

    # Stage 1: Ingest
    if session.current_stage in ("new", "ingest"):
        click.echo("\n=== Stage 1: Ingesting data ===")
        trip_data = _run_ingest(session)
        session.current_stage = "ingest"
        session.save()

    # Stage 2: Build skeleton
    if session.current_stage == "ingest":
        click.echo("\n=== Stage 2: Building trip skeleton ===")
        from post_trip_summary.pipeline.skeleton import build_skeleton
        trip_data = _load_trip_data(session)
        trip = build_skeleton(
            trip_data,
            gap_minutes=session.settings["cluster_time_gap_minutes"],
            distance_meters=session.settings["cluster_distance_meters"],
        )
        trip.name = session.name
        save_trip(trip, session.stage_file("skeleton"))
        session.current_stage = "skeleton"
        session.save()
        click.echo(f"Skeleton built: {sum(len(d.events) for d in trip.days)} events across {len(trip.days)} days")

    # Stage 3: Review skeleton
    if session.current_stage == "skeleton":
        trip = load_trip(session.stage_file("skeleton"))
        from post_trip_summary.pipeline.review_skeleton import review_skeleton
        trip = review_skeleton(trip)
        save_trip(trip, session.stage_file("skeleton_reviewed"))
        session.current_stage = "skeleton_reviewed"
        session.save()

    # Stage 4: Enrich
    if session.current_stage == "skeleton_reviewed":
        trip = load_trip(session.stage_file("skeleton_reviewed"))
        from post_trip_summary.pipeline.enrich import enrich_trip
        trip = enrich_trip(trip)
        save_trip(trip, session.stage_file("enriched"))
        session.current_stage = "enriched"
        session.save()

    # Stage 5: Review details
    if session.current_stage == "enriched":
        trip = load_trip(session.stage_file("enriched"))
        from post_trip_summary.pipeline.review_details import review_details
        trip = review_details(trip)
        save_trip(trip, session.stage_file("final"))
        session.current_stage = "final"
        session.save()

    click.echo(f"\nSession at stage: {session.current_stage}")
    click.echo(f"Run 'post-trip-summary preview {slug}' to preview, or 'post-trip-summary generate {slug}' to create outputs.")


@cli.command()
def config():
    """View and edit global settings."""
    from post_trip_summary.settings import load_settings, ensure_settings_file, SETTINGS_FILE
    settings_path = ensure_settings_file()
    settings = load_settings()
    click.echo(f"Settings file: {settings_path}")
    click.echo(f"Vision provider: {settings['vision']['provider']}")
    click.echo(f"Vision model: {settings['vision'].get(settings['vision']['provider'] + '_model', 'default')}")
    if click.confirm("Open settings file for editing?", default=False):
        click.edit(filename=str(settings_path))


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


@cli.command()
@click.argument("slug")
@click.option("--port", default=8765, help="Preview server port")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def preview(slug: str, port: int, base_dir: Path | None):
    """Preview trip outputs in browser."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    stage = session.current_stage
    if stage not in ("enriched", "final", "generated"):
        click.echo(f"No data to preview yet (stage: {stage}). Run 'resume' first.")
        raise SystemExit(1)
    from post_trip_summary.serialization import load_trip
    trip_file = session.stage_file("final") if session.stage_file("final").exists() else session.stage_file("enriched")
    trip = load_trip(trip_file)
    from post_trip_summary.preview.server import run_preview
    run_preview(trip, port=port)


@cli.command()
@click.argument("slug")
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, hidden=True)
def generate(slug: str, base_dir: Path | None):
    """Generate final output files."""
    base = base_dir or DEFAULT_BASE_DIR
    session = load_session(slug, base_dir=base)
    final_file = session.stage_file("final")
    if not final_file.exists():
        click.echo("No final data. Run 'resume' to complete the pipeline first.")
        raise SystemExit(1)

    from post_trip_summary.serialization import load_trip
    from post_trip_summary.output.photo_prep import prepare_photos
    from post_trip_summary.output.detailed_record import generate_detailed_record
    from post_trip_summary.output.shareable_pdf import generate_shareable_pdf
    from post_trip_summary.output.blog_post import generate_blog_post

    trip = load_trip(final_file)
    output_dir = session.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo("\n=== Generating outputs ===")

    click.echo("  Preparing photos...")
    prepare_photos(trip, output_dir)

    click.echo("  Generating detailed record...")
    generate_detailed_record(trip, output_dir / "detailed-record.html")

    click.echo("  Generating route map...")
    map_path = _generate_static_map(trip, output_dir)

    click.echo("  Generating shareable summary...")
    generate_shareable_pdf(trip, output_dir / "shareable-summary.pdf", map_image=map_path)

    click.echo("  Generating blog post...")
    generate_blog_post(trip, output_dir / "blog-post.html")

    session.current_stage = "generated"
    session.save()
    click.echo(f"\nOutputs saved to: {output_dir}")


def _generate_static_map(trip, output_dir) -> str | None:
    """Generate a static map image showing major stops. Returns relative path or None."""
    try:
        from staticmap import StaticMap, CircleMarker
        m = StaticMap(800, 400)
        for day in trip.days:
            for event in day.events:
                if event.location.lat and event.location.lon:
                    m.add_marker(CircleMarker((event.location.lon, event.location.lat), "#e74c3c", 8))
        if m.markers:
            map_path = output_dir / "route-map.png"
            image = m.render()
            image.save(str(map_path))
            return "route-map.png"
    except Exception as e:
        click.echo(f"  Warning: Map generation failed ({e}). Skipping.")
    return None


def _run_ingest(session) -> dict:
    """Run all ingest modules based on configured inputs."""
    import json

    trip_data = {
        "photos": [],
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }

    # Photos
    photos_path = session.inputs.get("photos")
    if photos_path:
        click.echo(f"  Scanning photos: {photos_path}")
        from post_trip_summary.pipeline.ingest.photos import ingest_photos
        trip_data["photos"] = ingest_photos(Path(photos_path))
        click.echo(f"    Found {len(trip_data['photos'])} photos")

    # Excel
    excel_path = session.inputs.get("excel")
    if excel_path:
        click.echo(f"  Parsing Excel: {excel_path}")
        from post_trip_summary.pipeline.ingest.excel import ingest_excel
        excel_data = ingest_excel(Path(excel_path))
        trip_data["accommodations"] = excel_data["accommodations"]
        trip_data["transits"] = excel_data["transits"]
        trip_data["activities"] = excel_data["activities"]
        trip_data["expenses"].extend(excel_data["expenses"])

    # Credit card
    cc_path = session.inputs.get("credit_card")
    if cc_path:
        click.echo(f"  Parsing credit card CSV: {cc_path}")
        from post_trip_summary.pipeline.ingest.credit_card import ingest_credit_card
        trip_data["expenses"].extend(ingest_credit_card(Path(cc_path)))

    # Google Maps
    gm_path = session.inputs.get("google_maps")
    if gm_path:
        click.echo(f"  Parsing Google Maps timeline: {gm_path}")
        from post_trip_summary.pipeline.ingest.google_maps import ingest_google_maps
        trip_data["google_maps"] = ingest_google_maps(Path(gm_path))

    # Apple Health
    ah_path = session.inputs.get("apple_health")
    if ah_path:
        click.echo(f"  Parsing Apple Health: {ah_path}")
        from post_trip_summary.pipeline.ingest.apple_health import ingest_apple_health
        trip_data["apple_health"] = ingest_apple_health(Path(ah_path))

    # Day One
    do_path = session.inputs.get("dayone")
    if do_path:
        click.echo(f"  Parsing Day One: {do_path}")
        from post_trip_summary.pipeline.ingest.dayone import ingest_dayone
        trip_data["dayone"] = ingest_dayone(Path(do_path))

    # Save raw trip data
    data_file = session.session_dir / "trip_data.json"
    # Serialize trip_data (contains model objects, need custom handling)
    from post_trip_summary.serialization import encode_value
    data_file.write_text(json.dumps(encode_value(trip_data), indent=2), encoding="utf-8")

    return trip_data


def _load_trip_data(session) -> dict:
    """Load raw trip data from disk."""
    import json
    from post_trip_summary.serialization import decode_value
    data_file = session.session_dir / "trip_data.json"
    raw = json.loads(data_file.read_text(encoding="utf-8"))
    return decode_value(raw)
