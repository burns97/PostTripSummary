# tests/test_quality.py
"""Tests for photo quality scoring."""
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from post_trip_summary.models import Photo
from post_trip_summary.pipeline.quality import (
    _normalize,
    _score_colorfulness,
    _score_exposure,
    _score_sharpness,
    apply_quality_cull,
    score_photos,
)


def _photo(path: Path = Path("x.jpg"), quality_score=None, is_kept=True):
    p = Photo(path=path, timestamp=datetime(2024, 1, 1), gps=None)
    p.quality_score = quality_score
    p.is_kept = is_kept
    return p


def _save_image(path: Path, img: Image.Image):
    img.save(str(path), "JPEG")


def test_sharp_scores_higher_than_blurry():
    """A high-contrast pattern should score higher sharpness than solid color."""
    # Sharp: checkerboard pattern
    sharp = Image.new("L", (100, 100), 0)
    arr = np.array(sharp)
    arr[::2, ::2] = 255
    arr[1::2, 1::2] = 255
    sharp = Image.fromarray(arr).convert("RGB")

    # Blurry: solid gray
    blurry = Image.new("RGB", (100, 100), (128, 128, 128))

    assert _score_sharpness(sharp) > _score_sharpness(blurry)


def test_colorful_scores_higher_than_gray():
    """An RGB gradient should score higher colorfulness than grayscale."""
    # Colorful: red/green/blue vertical stripes
    colorful = Image.new("RGB", (90, 30))
    arr = np.array(colorful)
    arr[:, :30] = [255, 0, 0]
    arr[:, 30:60] = [0, 255, 0]
    arr[:, 60:] = [0, 0, 255]
    colorful = Image.fromarray(arr)

    # Gray
    gray = Image.new("RGB", (90, 30), (128, 128, 128))

    assert _score_colorfulness(colorful) > _score_colorfulness(gray)


def test_good_exposure_scores_higher_than_blown():
    """A mid-tone image should score better exposure than all-white."""
    midtone = Image.new("RGB", (100, 100), (128, 128, 128))
    blown = Image.new("RGB", (100, 100), (255, 255, 255))

    assert _score_exposure(midtone) > _score_exposure(blown)


def test_normalize_range():
    """Known values should normalize to 0-100 range."""
    result = _normalize([10.0, 20.0, 30.0, 40.0, 50.0])
    assert result[0] == 0.0
    assert result[-1] == 100.0
    assert result[2] == pytest.approx(50.0)


def test_normalize_equal_values():
    """Equal values should all normalize to 50."""
    result = _normalize([5.0, 5.0, 5.0])
    assert all(v == 50.0 for v in result)


def test_normalize_empty():
    assert _normalize([]) == []


def test_apply_cull_percentile():
    """Bottom 20% of 10 photos → 2 culled (if below absolute floor)."""
    photos = [_photo(quality_score=float(i)) for i in range(10)]  # 0..9
    culled = apply_quality_cull(photos, percentile=20.0)
    assert culled == 2
    assert not photos[0].is_kept
    assert not photos[1].is_kept
    assert photos[2].is_kept


def test_apply_cull_floor():
    """Photos above absolute floor (25) should not be culled even if in bottom percentile."""
    # All photos have scores 50-59 (well above floor of 25)
    photos = [_photo(quality_score=50.0 + i) for i in range(10)]
    culled = apply_quality_cull(photos, percentile=30.0)
    assert culled == 0
    assert all(p.is_kept for p in photos)


def test_apply_cull_no_scored_photos():
    """No scored photos → no culling."""
    photos = [_photo(quality_score=None) for _ in range(5)]
    assert apply_quality_cull(photos) == 0


def test_score_photos_sets_quality_score(tmp_path):
    """Real JPEG files get non-None quality scores."""
    paths = []
    for i in range(3):
        p = tmp_path / f"photo_{i}.jpg"
        img = Image.new("RGB", (200, 200), (100 + i * 50, 80, 60))
        _save_image(p, img)
        paths.append(p)

    photos = [_photo(path=p) for p in paths]
    score_photos(photos)

    for photo in photos:
        assert photo.quality_score is not None
        assert 0.0 <= photo.quality_score <= 100.0


def test_score_photos_handles_missing_file(tmp_path):
    """Missing files get score 0.0, don't crash the batch."""
    good_path = tmp_path / "good.jpg"
    Image.new("RGB", (100, 100), (128, 128, 128)).save(str(good_path), "JPEG")

    photos = [
        _photo(path=good_path),
        _photo(path=tmp_path / "missing.jpg"),
    ]
    score_photos(photos)

    assert photos[0].quality_score is not None
    assert photos[0].quality_score > 0
    assert photos[1].quality_score == 0.0
