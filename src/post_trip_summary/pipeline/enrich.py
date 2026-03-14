# src/post_trip_summary/pipeline/enrich.py
"""Stage 4: Enrich events with AI vision analysis."""
import click
from pathlib import Path

from post_trip_summary.models import Trip, Photo
from post_trip_summary.settings import get_vision_settings
from post_trip_summary.vision.client import create_provider
from post_trip_summary.vision.triage import plan_enrichment, estimate_batch_cost


def _select_highlights(photos: list[Photo], max_count: int = 5) -> list[Photo]:
    """Mark the best photos as highlights. Returns the highlighted subset."""
    # Spread evenly across the photo set
    if len(photos) <= max_count:
        for p in photos:
            p.is_highlight = True
        return photos

    step = len(photos) / max_count
    selected = []
    for i in range(max_count):
        idx = int(i * step)
        photos[idx].is_highlight = True
        selected.append(photos[idx])
    return selected


def _read_image(path: Path) -> tuple[bytes, str]:
    """Read image file and determine media type."""
    suffix = path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".heic": "image/heic",
        ".heif": "image/heif", ".webp": "image/webp",
        ".tiff": "image/tiff", ".tif": "image/tiff",
    }
    media_type = media_types.get(suffix, "image/jpeg")
    return path.read_bytes(), media_type


def enrich_trip(trip: Trip, auto_approve: bool = False) -> Trip:
    """Run vision analysis on representative photos and update events."""
    # Load vision settings and create provider
    vs = get_vision_settings()
    provider = create_provider(vs["provider"], api_key=vs.get("api_key"), model=vs.get("model"))

    # Collect all events with photos
    all_events = [event for day in trip.days for event in day.events if event.photos]

    # Plan which photos to analyze
    enrichment_plan = plan_enrichment(all_events)
    total_images = sum(len(item["photos"]) for item in enrichment_plan)

    if total_images == 0:
        click.echo("No photos need vision analysis.")
        return trip

    # Cost gate
    estimated_cost = estimate_batch_cost(total_images, provider)
    click.echo("\n=== Vision Enrichment ===")
    click.echo(f"Provider: {vs['provider']} ({vs['model']})")
    click.echo(f"Photos to analyze: {total_images} across {len(enrichment_plan)} events")
    if estimated_cost == 0.0:
        click.echo("Estimated cost: Free (Gemini Flash free tier)")
    else:
        click.echo(f"Estimated cost: ${estimated_cost:.2f}")

    if not auto_approve:
        choice = click.prompt(
            "\n[a]pprove / [r]educe scope / [s]kip enrichment",
            type=str, default="a",
        ).lower().strip()

        if choice in ("s", "skip"):
            click.echo("Skipping enrichment. Selecting highlights only.")
            for event in all_events:
                _select_highlights(event.photos)
            return trip
        elif choice in ("r", "reduce"):
            click.echo("Reducing to most uncertain events only.")
            enrichment_plan = [p for p in enrichment_plan if p["purpose"] != "scene"]
            total_images = sum(len(item["photos"]) for item in enrichment_plan)
            new_cost = estimate_batch_cost(total_images, provider)
            if new_cost == 0.0:
                click.echo(f"Reduced to {total_images} images. Cost: Free")
            else:
                click.echo(f"Reduced to {total_images} images. New estimate: ${new_cost:.2f}")

    # Run analysis
    for item in enrichment_plan:
        event = item["event"]
        photos = item["photos"]
        purpose = item["purpose"]

        best_description = ""
        best_landmark = None

        for photo in photos:
            try:
                image_data, media_type = _read_image(photo.path)
                result = provider.analyze(image_data, media_type, purpose)
                photo.ai_description = result.description
                if result.landmark and not best_landmark:
                    best_landmark = result.landmark
                if result.description and not best_description:
                    best_description = result.description
            except Exception as e:
                click.echo(f"  Warning: Failed to analyze {photo.path.name}: {e}")

        # Update event
        if best_description and not event.description:
            event.description = best_description
        if best_landmark and event.name in ("Unknown", event.location.city, ""):
            event.name = best_landmark

        # Select highlights
        _select_highlights(event.photos)

    click.echo(f"\nEnrichment complete. Analyzed {total_images} photos.")
    return trip
