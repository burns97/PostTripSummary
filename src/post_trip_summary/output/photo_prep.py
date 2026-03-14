# src/post_trip_summary/output/photo_prep.py
"""Prepare highlight photos for output (resize and copy)."""
from pathlib import Path
from PIL import Image

from post_trip_summary.models import Trip, Photo

MAX_WIDTH = 1920


def collect_highlight_photos(trip: Trip) -> list[Photo]:
    """Gather all highlight photos from the trip."""
    highlights = []
    for day in trip.days:
        for event in day.events:
            for photo in event.photos:
                if photo.is_highlight:
                    highlights.append(photo)
    return highlights


def prepare_photos(trip: Trip, output_dir: Path) -> None:
    """Resize and copy highlight photos to output/photos/."""
    photos_dir = output_dir / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)

    for photo in collect_highlight_photos(trip):
        src = photo.path
        dest = photos_dir / src.name
        if not src.exists():
            continue
        try:
            img = Image.open(src)
            if img.width > MAX_WIDTH:
                ratio = MAX_WIDTH / img.width
                new_size = (MAX_WIDTH, int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            img.save(dest, quality=85)
        except Exception:
            # Fall back to simple copy
            import shutil
            shutil.copy2(src, dest)
