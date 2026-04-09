"""Thumbnail grid (montage) generation for vision API batch analysis."""
from __future__ import annotations

import math
from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from post_trip_summary.models import Photo


def _temporal_sample(photos: list[Photo], max_count: int) -> list[Photo]:
    """Sample photos evenly by index, always including first and last."""
    n = len(photos)
    if n <= max_count:
        return list(photos)
    # Pick max_count indices spread evenly, always including 0 and n-1
    indices = [round(i * (n - 1) / (max_count - 1)) for i in range(max_count)]
    return [photos[i] for i in indices]


def build_montage(
    photos: list[Photo],
    thumb_size: int = 256,
    cols: int = 5,
    max_count: int = 20,
) -> tuple[bytes, dict[int, Photo]]:
    """Build a numbered thumbnail grid from a list of photos.

    Returns (jpeg_bytes, photo_map) where photo_map is {1: Photo, 2: Photo, ...}.
    """
    sampled = _temporal_sample(photos, max_count)
    n = len(sampled)
    if n == 0:
        # Return a minimal 1x1 white JPEG and empty map
        img = Image.new("RGB", (1, 1), "white")
        buf = BytesIO()
        img.save(buf, "JPEG")
        return buf.getvalue(), {}

    rows = math.ceil(n / cols)
    label_h = 20
    cell_h = label_h + thumb_size
    canvas_w = cols * thumb_size
    canvas_h = rows * cell_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
    draw = ImageDraw.Draw(canvas)

    # Try to get a basic font; fall back to default
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except (OSError, IOError):
        font = ImageFont.load_default()

    photo_map: dict[int, Photo] = {}

    for idx, photo in enumerate(sampled):
        col = idx % cols
        row = idx // cols
        x = col * thumb_size
        y = row * cell_h
        grid_num = idx + 1
        photo_map[grid_num] = photo

        # Draw label
        draw.text((x + 4, y + 2), str(grid_num), fill="black", font=font)

        # Load and paste thumbnail
        try:
            with Image.open(photo.path) as img:
                img = img.convert("RGB")
                img.thumbnail((thumb_size, thumb_size))
                # Center the thumbnail in the cell
                paste_x = x + (thumb_size - img.width) // 2
                paste_y = y + label_h + (thumb_size - img.height) // 2
                canvas.paste(img, (paste_x, paste_y))
        except Exception:
            # Placeholder for corrupt/missing images
            draw.rectangle(
                [x, y + label_h, x + thumb_size - 1, y + cell_h - 1],
                fill="#CCCCCC",
                outline="#999999",
            )
            draw.text((x + 4, y + label_h + 4), "?", fill="red", font=font)

    buf = BytesIO()
    canvas.save(buf, "JPEG", quality=85)
    return buf.getvalue(), photo_map
