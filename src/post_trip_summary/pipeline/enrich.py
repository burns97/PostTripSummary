# src/post_trip_summary/pipeline/enrich.py
"""Stage 4: Enrich events with AI vision analysis."""
import click
from pathlib import Path

from post_trip_summary.models import Trip, Photo
from post_trip_summary.settings import get_vision_settings
from post_trip_summary.vision.client import create_provider
from post_trip_summary.vision.triage import plan_enrichment, estimate_batch_cost


def _select_highlights(photos: list[Photo], max_count: int = 5) -> list[Photo]:
    """Mark the best kept photos as highlights. Returns the highlighted subset."""
    kept = [p for p in photos if p.is_kept]
    if not kept:
        return []

    if len(kept) <= max_count:
        for p in kept:
            p.is_highlight = True
        return kept

    step = len(kept) / max_count
    selected = []
    for i in range(max_count):
        idx = int(i * step)
        kept[idx].is_highlight = True
        selected.append(kept[idx])
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
    # Load vision settings and validate before creating provider
    vs = get_vision_settings()
    if not vs.get("api_key"):
        provider_name = vs["provider"]
        if provider_name == "gemini":
            env_hint = "GOOGLE_API_KEY"
        else:
            env_hint = "ANTHROPIC_API_KEY"
        click.echo(f"\nNo API key configured for vision provider '{provider_name}'.")
        click.echo(f"Set {env_hint} env var or add it to ~/.post-trip-summary/settings.toml")
        click.echo("Skipping enrichment. Selecting highlights only.")
        all_events = [event for day in trip.days for event in day.events if event.photos]
        for event in all_events:
            _select_highlights(event.photos)
        return trip

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
    from post_trip_summary.vision.gemini import QuotaExhaustedError
    from post_trip_summary.vision.prompts import build_context

    analyzed = 0
    failed = 0
    quota_exhausted = False
    event_count = len(enrichment_plan)
    for event_idx, item in enumerate(enrichment_plan, 1):
        event = item["event"]
        photos = item["photos"]
        purpose = item["purpose"]

        # Build context from event metadata to help the vision model
        loc = event.location
        context = build_context(
            timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
            city=loc.city if loc else "",
            country=loc.country if loc else "",
            poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
        )

        best_description = ""
        best_landmark = None

        if not quota_exhausted:
            click.echo(f"  [{event_idx}/{event_count}] {event.name} ({len(photos)} photos)...", nl=False)

        for photo in photos:
            if quota_exhausted:
                break
            try:
                image_data, media_type = _read_image(photo.path)
                result = provider.analyze(image_data, media_type, purpose, context=context)
                photo.ai_description = result.description
                analyzed += 1
                if result.landmark and not best_landmark:
                    best_landmark = result.landmark
                if result.description and not best_description:
                    best_description = result.description
            except QuotaExhaustedError:
                click.echo(" quota exhausted")
                click.echo("Stopping enrichment. Remaining events will use highlights only.")
                quota_exhausted = True
            except Exception as e:
                failed += 1
                click.echo(f"\n    Warning: {photo.path.name}: {e}", nl=False)

        if not quota_exhausted:
            landmark_note = f" -> {best_landmark}" if best_landmark else ""
            click.echo(f" done{landmark_note}")

        # Update event
        if best_description and not event.description:
            event.description = best_description
        if best_landmark and event.name in ("Unknown", event.location.city, ""):
            event.name = best_landmark

        # Select highlights
        _select_highlights(event.photos)

    # --- Pass 2: Synthesize event descriptions from highlight photos ---
    if not quota_exhausted:
        from post_trip_summary.vision.prompts import get_prompt

        synth_count = 0
        for item in enrichment_plan:
            event = item["event"]
            described_highlights = [
                p for p in event.photos
                if p.is_kept and p.is_highlight and p.ai_description
            ]
            if len(described_highlights) < 2:
                continue

            desc_lines = [
                f"{i + 1}. {p.ai_description}"
                for i, p in enumerate(described_highlights)
            ]
            descriptions_text = "\n".join(desc_lines)

            loc = event.location
            context = build_context(
                timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
                city=loc.city if loc else "",
                country=loc.country if loc else "",
                poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
            )

            prompt = get_prompt(
                "synthesize",
                context=context,
                image_count=len(described_highlights),
                descriptions=descriptions_text,
            )
            try:
                event.description = provider.synthesize(prompt)
                synth_count += 1
            except Exception:
                pass  # Keep the best single description from pass 1

        if synth_count:
            click.echo(f"  Synthesized {synth_count} event descriptions from highlights.")

    summary = f"\nEnrichment complete. Analyzed {analyzed}/{total_images} photos."
    if failed:
        summary += f" ({failed} failed)"
    click.echo(summary)
    return trip


def enrich_trip_headless(
    trip: Trip,
    mode: str = "full",
    progress_callback=None,
) -> Trip:
    """Run vision enrichment without CLI interaction.

    Args:
        trip: The trip to enrich.
        mode: "full" (all photos), "reduced" (non-scene only), or "skip" (highlights only).
        progress_callback: Optional callable(phase, current, total, label).

    Returns:
        The enriched trip.
    """
    def _progress(phase, current, total, label=""):
        if progress_callback:
            progress_callback(phase, current, total, label)

    all_events = [event for day in trip.days for event in day.events if event.photos]

    if mode == "skip":
        for event in all_events:
            _select_highlights(event.photos)
        _progress("done", 0, 0, "Skipped enrichment, highlights selected")
        return trip

    # Create vision provider
    vs = get_vision_settings()
    if not vs.get("api_key"):
        # No API key -- just select highlights
        for event in all_events:
            _select_highlights(event.photos)
        _progress("done", 0, 0, "No API key; highlights selected only")
        return trip

    provider = create_provider(vs["provider"], api_key=vs.get("api_key"), model=vs.get("model"))

    # Plan enrichment
    enrichment_plan = plan_enrichment(all_events)
    total_images = sum(len(item["photos"]) for item in enrichment_plan)

    if mode == "reduced":
        enrichment_plan = [p for p in enrichment_plan if p["purpose"] != "scene"]
        total_images = sum(len(item["photos"]) for item in enrichment_plan)

    if total_images == 0:
        for event in all_events:
            _select_highlights(event.photos)
        _progress("done", 0, 0, "No photos need analysis")
        return trip

    # --- Pass 1: Per-photo analysis ---
    from post_trip_summary.vision.gemini import QuotaExhaustedError
    from post_trip_summary.vision.prompts import build_context

    analyzed = 0
    failed = 0
    quota_exhausted = False
    event_count = len(enrichment_plan)

    for event_idx, item in enumerate(enrichment_plan, 1):
        event = item["event"]
        photos = item["photos"]
        purpose = item["purpose"]

        loc = event.location
        context = build_context(
            timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
            city=loc.city if loc else "",
            country=loc.country if loc else "",
            poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
        )

        best_description = ""
        best_landmark = None

        _progress("analyzing", analyzed, total_images,
                  f"[{event_idx}/{event_count}] {event.name}")

        for photo in photos:
            if quota_exhausted:
                break
            try:
                image_data, media_type = _read_image(photo.path)
                result = provider.analyze(image_data, media_type, purpose, context=context)
                photo.ai_description = result.description
                analyzed += 1
                if result.landmark and not best_landmark:
                    best_landmark = result.landmark
                if result.description and not best_description:
                    best_description = result.description
                _progress("analyzing", analyzed, total_images,
                          f"[{event_idx}/{event_count}] {event.name}")
            except QuotaExhaustedError:
                quota_exhausted = True
            except Exception:
                failed += 1

        # Update event
        if best_description and not event.description:
            event.description = best_description
        if best_landmark and event.name in ("Unknown", event.location.city, ""):
            event.name = best_landmark

        # Select highlights
        _select_highlights(event.photos)

    # Select highlights for any events not in the plan
    plan_event_ids = {item["event"].id for item in enrichment_plan}
    for event in all_events:
        if event.id not in plan_event_ids:
            _select_highlights(event.photos)

    return trip


def synthesize_event_descriptions(trip: Trip, progress_callback=None) -> Trip:
    """Synthesize unified event descriptions from highlight photo descriptions.

    This is a text-only pass (no image tokens) that should run AFTER the user
    has finalized highlight selections. For events with 2+ described highlights,
    it asks the vision provider to weave the individual descriptions into a
    cohesive 2-4 sentence event summary.
    """
    vs = get_vision_settings()
    if not vs.get("api_key"):
        return trip

    provider = create_provider(vs["provider"], api_key=vs.get("api_key"), model=vs.get("model"))
    from post_trip_summary.vision.prompts import build_context, get_prompt

    all_events = [event for day in trip.days for event in day.events if event.photos]
    synth_count = 0

    for event in all_events:
        described_highlights = [
            p for p in event.photos
            if p.is_kept and p.is_highlight and p.ai_description
        ]
        if len(described_highlights) < 2:
            continue

        synth_count += 1
        if progress_callback:
            progress_callback("synthesizing", synth_count, 0, f"Synthesizing: {event.name}")

        desc_lines = [
            f"{i + 1}. {p.ai_description}"
            for i, p in enumerate(described_highlights)
        ]
        descriptions_text = "\n".join(desc_lines)

        loc = event.location
        context = build_context(
            timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
            city=loc.city if loc else "",
            country=loc.country if loc else "",
            poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
        )

        prompt = get_prompt(
            "synthesize",
            context=context,
            image_count=len(described_highlights),
            descriptions=descriptions_text,
        )
        try:
            event.description = provider.synthesize(prompt)
        except Exception:
            pass  # Keep the existing description

    return trip
