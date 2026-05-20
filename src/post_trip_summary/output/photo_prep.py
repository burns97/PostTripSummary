# src/post_trip_summary/output/photo_prep.py
"""Prepare photos referenced by generated outputs."""
from pathlib import Path
from PIL import Image

from post_trip_summary.models import Event, Trip, Photo
from post_trip_summary.output.trip_story import days_with_story_content, select_cover_photo

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

MAX_WIDTH = 1920


def collect_highlight_photos(trip: Trip) -> list[Photo]:
    """Gather all highlight photos from the trip."""
    highlights = []
    for day in trip.days:
        for event in day.events:
            for photo in event.photos:
                if photo.is_kept and photo.is_highlight:
                    highlights.append(photo)
    return highlights


def collect_output_photos(trip: Trip) -> list[Photo]:
    """Gather photos referenced by generated HTML outputs."""
    photos: list[Photo] = []
    seen: set[Path] = set()

    def add(photo: Photo) -> None:
        if not photo.is_kept or photo.path in seen:
            return
        seen.add(photo.path)
        photos.append(photo)

    for photo in collect_highlight_photos(trip):
        add(photo)

    cover_photo = select_cover_photo(trip)
    if cover_photo is not None:
        add(cover_photo)

    for day in days_with_story_content(trip):
        for event in day.events:
            for photo in _trip_story_event_photos(event):
                add(photo)

    return photos


def _trip_story_event_photos(event: Event) -> list[Photo]:
    kept_photos = [photo for photo in event.photos if photo.is_kept]
    event_highlights = [photo for photo in kept_photos if photo.is_highlight]
    if event_highlights:
        return event_highlights[:6]
    return kept_photos[:3]


def prepare_photos(trip: Trip, output_dir: Path) -> None:
    """Resize and convert photos referenced by outputs to JPEG in output/photos/."""
    photos_dir = output_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    for photo in collect_output_photos(trip):
        src = photo.path
        # Always save as .jpg for browser compatibility
        dest = photos_dir / (src.stem + ".jpg")
        if not src.exists():
            continue
        try:
            img = Image.open(src)
            if img.width > MAX_WIDTH:
                ratio = MAX_WIDTH / img.width
                new_size = (MAX_WIDTH, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(dest, format="JPEG", quality=85)
        except Exception:
            # Fall back to simple copy (at least preserves the file)
            import shutil
            shutil.copy2(src, photos_dir / src.name)
