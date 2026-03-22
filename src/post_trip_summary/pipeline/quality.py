# src/post_trip_summary/pipeline/quality.py
"""Automated photo quality scoring — sharpness, colorfulness, exposure."""
from __future__ import annotations

import numpy as np
from PIL import Image
from scipy.ndimage import laplace

from post_trip_summary.models import Photo


def _score_sharpness(img: Image.Image) -> float:
    """Laplacian variance on grayscale. Higher = sharper."""
    gray = np.array(img.convert("L"), dtype=np.float64)
    return float(laplace(gray).var())


def _score_colorfulness(img: Image.Image) -> float:
    """Hasler & Süsstrunk colorfulness metric. Higher = more colorful."""
    arr = np.array(img, dtype=np.float64)
    if arr.ndim < 3 or arr.shape[2] < 3:
        return 0.0
    R, G, B = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    rg = R - G
    yb = 0.5 * (R + G) - B
    std = np.sqrt(rg.std() ** 2 + yb.std() ** 2)
    mean = np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
    return float(std + 0.3 * mean)


def _score_exposure(img: Image.Image) -> float:
    """Score based on histogram — penalize extreme dark/bright concentration.
    Returns higher values for well-exposed images."""
    gray = img.convert("L")
    hist = gray.histogram()  # 256 bins
    total = sum(hist)
    if total == 0:
        return 0.0
    dark_frac = sum(hist[:15]) / total
    bright_frac = sum(hist[240:]) / total
    extreme = dark_frac + bright_frac
    # 0 extreme → score 100, 1.0 extreme → score 0
    return max(0.0, 100.0 * (1.0 - extreme))


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize values to 0-100 range."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [50.0] * len(values)
    return [100.0 * (v - lo) / (hi - lo) for v in values]


def score_photos(photos: list[Photo], thumbnail_size: int = 512, progress_callback=None) -> None:
    """Score all photos in-place. Sets photo.quality_score (0-100)."""
    if not photos:
        return

    raw_sharp: list[float] = []
    raw_color: list[float] = []
    raw_exposure: list[float] = []
    valid_indices: list[int] = []

    for i, photo in enumerate(photos):
        if progress_callback:
            progress_callback("scoring", i + 1, len(photos), photo.path.name)
        try:
            img = Image.open(photo.path)
            img.thumbnail((thumbnail_size, thumbnail_size))
            raw_sharp.append(_score_sharpness(img))
            raw_color.append(_score_colorfulness(img))
            raw_exposure.append(_score_exposure(img))
            valid_indices.append(i)
        except Exception:
            photo.quality_score = 0.0

    norm_sharp = _normalize(raw_sharp)
    norm_color = _normalize(raw_color)
    norm_exposure = _normalize(raw_exposure)

    for j, idx in enumerate(valid_indices):
        photos[idx].quality_score = round(
            0.5 * norm_sharp[j] + 0.3 * norm_color[j] + 0.2 * norm_exposure[j], 1
        )


def apply_quality_cull(photos: list[Photo], percentile: float = 15.0) -> int:
    """Set is_kept=False on bottom percentile. Returns count culled.
    Also enforces absolute floor: only cull if score < 25."""
    scored = [p for p in photos if p.quality_score is not None]
    if not scored:
        return 0

    scores = sorted(p.quality_score for p in scored)
    threshold_idx = max(0, int(len(scores) * percentile / 100.0) - 1)
    percentile_threshold = scores[threshold_idx]
    # Use the stricter of percentile threshold and absolute floor
    threshold = min(percentile_threshold, 25.0)

    culled = 0
    for photo in photos:
        if photo.quality_score is not None and photo.quality_score <= threshold:
            photo.is_kept = False
            culled += 1
    return culled
