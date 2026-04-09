"""Tests for vision.montage -- thumbnail grid generation."""
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from post_trip_summary.models import Photo


def _photo(name, minutes=0):
    return Photo(path=Path(f"/fake/{name}.jpg"), timestamp=datetime(2026, 1, 1, 10, minutes), gps=None)


def _make_test_image(path, color="red", size=(800, 600)):
    img = Image.new("RGB", size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG")


class TestTemporalSample:
    def test_returns_all_when_under_max(self):
        from post_trip_summary.vision.montage import _temporal_sample
        photos = [_photo("a", 0), _photo("b", 5), _photo("c", 10)]
        assert len(_temporal_sample(photos, max_count=5)) == 3

    def test_samples_evenly_when_over_max(self):
        from post_trip_summary.vision.montage import _temporal_sample
        photos = [_photo(f"p{i}", i) for i in range(30)]
        result = _temporal_sample(photos, max_count=10)
        assert len(result) == 10
        assert result[0].path.name == "p0.jpg"
        assert result[-1].path.name == "p29.jpg"

    def test_empty_list(self):
        from post_trip_summary.vision.montage import _temporal_sample
        assert _temporal_sample([], max_count=5) == []


class TestBuildMontage:
    def test_produces_valid_jpeg(self, tmp_path):
        from post_trip_summary.vision.montage import build_montage
        photos = []
        for i in range(6):
            p = _photo(f"img{i}", i)
            p.path = tmp_path / f"img{i}.jpg"
            _make_test_image(p.path)
            photos.append(p)
        data, photo_map = build_montage(photos)
        assert Image.open(BytesIO(data)).format == "JPEG"
        assert len(photo_map) == 6

    def test_respects_thumb_size(self, tmp_path):
        from post_trip_summary.vision.montage import build_montage
        photos = []
        for i in range(4):
            p = _photo(f"img{i}", i)
            p.path = tmp_path / f"img{i}.jpg"
            _make_test_image(p.path)
            photos.append(p)
        data, _ = build_montage(photos, thumb_size=128, cols=2)
        img = Image.open(BytesIO(data))
        assert img.width == 2 * 128
        assert img.height >= 2 * 128

    def test_max_count_limits_photos(self, tmp_path):
        from post_trip_summary.vision.montage import build_montage
        photos = []
        for i in range(25):
            p = _photo(f"img{i}", i)
            p.path = tmp_path / f"img{i}.jpg"
            _make_test_image(p.path)
            photos.append(p)
        _, photo_map = build_montage(photos, max_count=10)
        assert len(photo_map) == 10

    def test_photo_map_maps_grid_index_to_photo(self, tmp_path):
        from post_trip_summary.vision.montage import build_montage
        photos = []
        for i in range(3):
            p = _photo(f"img{i}", i)
            p.path = tmp_path / f"img{i}.jpg"
            _make_test_image(p.path)
            photos.append(p)
        _, photo_map = build_montage(photos)
        assert set(photo_map.keys()) == {1, 2, 3}
        assert photo_map[1].path.name == "img0.jpg"
