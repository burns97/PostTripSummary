"""Local model prefill for draft photo descriptions."""
from __future__ import annotations

from dataclasses import dataclass

from post_trip_summary.models import Event, Trip
from post_trip_summary.pipeline.enrich import _read_image
from post_trip_summary.settings import load_settings
from post_trip_summary.vision.client import VisionProvider, create_provider
from post_trip_summary.vision.prompts import build_context, get_prompt
from post_trip_summary.vision.triage import select_representatives


@dataclass
class LocalPrefillStats:
    events_seen: int = 0
    photos_attempted: int = 0
    photos_described: int = 0
    skipped_existing: int = 0
    failed: int = 0
    summaries_written: int = 0


def prefill_trip_with_local_descriptions(
    trip: Trip,
    provider: VisionProvider | None = None,
    max_photos_per_event: int = 2,
    overwrite: bool = False,
    progress_callback=None,
) -> LocalPrefillStats:
    """Draft photo descriptions with a local Ollama model.

    The pass is intentionally conservative: it samples a small representative
    set for each event and preserves existing photo/event text unless
    ``overwrite`` is explicitly requested.
    """
    local_provider = provider or _create_local_provider()
    stats = LocalPrefillStats()
    events = [
        event
        for day in trip.days
        for event in day.events
        if any(photo.is_kept for photo in event.photos)
    ]

    for index, event in enumerate(events, 1):
        stats.events_seen += 1
        if progress_callback:
            progress_callback("local_prefill", index, len(events), event.name)

        kept = [photo for photo in event.photos if photo.is_kept]
        selected = select_representatives(kept, max_count=max(1, max_photos_per_event))
        context = _event_context(event)

        for photo in selected:
            if photo.ai_description and not overwrite:
                stats.skipped_existing += 1
                continue

            stats.photos_attempted += 1
            try:
                image_data, media_type = _read_image(photo.path)
                result = local_provider.analyze(
                    image_data,
                    media_type=media_type,
                    purpose="scene",
                    context=context,
                )
            except Exception:
                stats.failed += 1
                continue

            description = (result.description or "").strip()
            if not description:
                continue
            photo.ai_description = description
            photo.is_highlight = True
            stats.photos_described += 1

        if _write_event_summary(event, local_provider, overwrite):
            stats.summaries_written += 1

    if progress_callback:
        progress_callback("done", len(events), len(events), "Local prefill complete")

    return stats


def _create_local_provider() -> VisionProvider:
    settings = load_settings()
    vision = settings["vision"]
    return create_provider(
        "ollama",
        model=vision.get("ollama_model", "gemma4:e2b"),
        base_url=vision.get("ollama_base_url", "http://localhost:11434"),
        timeout_seconds=vision.get("ollama_timeout_seconds", 120),
    )


def _event_context(event: Event) -> str:
    loc = event.location
    return build_context(
        timestamp=event.time_range[0].strftime("%Y-%m-%d %H:%M") if event.time_range else "",
        city=loc.city if loc else "",
        country=loc.country if loc else "",
        poi_name=loc.name if loc and loc.name not in ("Unknown", loc.city, "") else "",
        event_name=event.name,
    )


def _write_event_summary(
    event: Event,
    provider: VisionProvider,
    overwrite: bool,
) -> bool:
    if (event.summary or event.description) and not overwrite:
        return False

    described = [
        photo
        for photo in event.photos
        if photo.is_kept and photo.ai_description
    ]
    if not described:
        return False

    if len(described) == 1:
        summary = described[0].ai_description or ""
    else:
        desc_lines = [
            f"{index + 1}. {photo.ai_description}"
            for index, photo in enumerate(described)
            if photo.ai_description
        ]
        prompt = get_prompt(
            "synthesize",
            context=_event_context(event),
            image_count=len(desc_lines),
            descriptions="\n".join(desc_lines),
        )
        try:
            summary = provider.synthesize(prompt).strip()
        except Exception:
            summary = described[0].ai_description or ""

    if not summary:
        return False

    event.summary = summary
    if overwrite or not event.description:
        event.description = summary
    return True
