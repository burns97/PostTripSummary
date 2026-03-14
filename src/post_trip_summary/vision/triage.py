# src/post_trip_summary/vision/triage.py
"""Photo selection, deduplication, and cost estimation for vision API."""
from pathlib import Path

from post_trip_summary.models import Photo, Event
from post_trip_summary.vision.client import VisionClient


def is_confidently_identified(event: Event) -> bool:
    """An event is confident if confirmed by 2+ independent sources."""
    return len(event.sources) >= 2


def _deduplicate_by_hash(photos: list[Photo]) -> list[Photo]:
    """Remove perceptually similar photos using imagehash."""
    try:
        import imagehash
        from PIL import Image
    except ImportError:
        return photos

    seen_hashes = set()
    unique = []
    for photo in photos:
        try:
            img = Image.open(photo.path)
            h = str(imagehash.average_hash(img))
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique.append(photo)
        except Exception:
            unique.append(photo)  # Keep photos we can't hash
    return unique


def select_representatives(photos: list[Photo], max_count: int = 5) -> list[Photo]:
    """Select representative photos from a cluster for API analysis."""
    if len(photos) <= max_count:
        return list(photos)

    # Try deduplication first
    unique = _deduplicate_by_hash(photos)
    if len(unique) <= max_count:
        return unique

    # Spread evenly across the time range
    step = len(unique) / max_count
    selected = []
    for i in range(max_count):
        idx = int(i * step)
        selected.append(unique[idx])
    return selected


def estimate_batch_cost(num_images: int) -> float:
    """Estimate cost for analyzing a batch of images."""
    client = VisionClient.__new__(VisionClient)
    return client.estimate_cost(num_images)


def plan_enrichment(events: list[Event], max_per_event: int = 5) -> list[dict]:
    """Plan which photos to send to the API for each event.

    Returns a list of dicts: {"event": Event, "photos": [Photo], "purpose": str}
    Skips confidently identified events (only sends 1 for scene description).
    """
    plan = []
    for event in events:
        if not event.photos:
            continue

        if is_confidently_identified(event):
            # Already identified -- just get a scene description for 1 photo
            reps = select_representatives(event.photos, max_count=1)
            plan.append({"event": event, "photos": reps, "purpose": "scene"})
        else:
            reps = select_representatives(event.photos, max_count=max_per_event)
            plan.append({"event": event, "photos": reps, "purpose": "landmark"})

    return plan
