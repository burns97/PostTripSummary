# tests/test_ingest_photos.py
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
from post_trip_summary.pipeline.ingest.photos import scan_photos, extract_photo_metadata, SUPPORTED_EXTENSIONS


def test_supported_extensions():
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".heic" in SUPPORTED_EXTENSIONS
    assert ".mp4" not in SUPPORTED_EXTENSIONS


def test_extract_photo_metadata_with_gps():
    mock_tags = {
        "EXIF:DateTimeOriginal": "2026:03:05 16:30:00",
        "EXIF:GPSLatitude": 48.8584,
        "EXIF:GPSLongitude": 2.2945,
        "EXIF:GPSLatitudeRef": "N",
        "EXIF:GPSLongitudeRef": "E",
    }
    result = extract_photo_metadata(Path("/photos/img001.jpg"), mock_tags)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)
    assert result.gps is not None
    assert abs(result.gps[0] - 48.8584) < 0.001
    assert abs(result.gps[1] - 2.2945) < 0.001


def test_extract_photo_metadata_no_gps():
    mock_tags = {"EXIF:DateTimeOriginal": "2026:03:05 16:30:00"}
    result = extract_photo_metadata(Path("/photos/img002.jpg"), mock_tags)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)
    assert result.gps is None


def test_extract_photo_metadata_date_fallback():
    mock_tags = {"EXIF:CreateDate": "2026:03:05 16:30:00"}
    result = extract_photo_metadata(Path("/photos/img003.jpg"), mock_tags)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)


def test_extract_photo_metadata_filename_fallback():
    mock_tags = {}
    result = extract_photo_metadata(Path("/photos/IMG_20260305_163000.jpg"), mock_tags)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)


def test_extract_photo_metadata_south_west_gps():
    mock_tags = {
        "EXIF:DateTimeOriginal": "2026:03:05 10:00:00",
        "EXIF:GPSLatitude": 37.7749,
        "EXIF:GPSLongitude": 122.4194,
        "EXIF:GPSLatitudeRef": "S",
        "EXIF:GPSLongitudeRef": "W",
    }
    result = extract_photo_metadata(Path("/photos/img004.jpg"), mock_tags)
    assert result.gps[0] < 0
    assert result.gps[1] < 0


def test_scan_photos(tmp_path):
    (tmp_path / "photo1.jpg").write_text("fake")
    (tmp_path / "photo2.heic").write_text("fake")
    (tmp_path / "video.mp4").write_text("fake")
    (tmp_path / "notes.txt").write_text("fake")
    sub = tmp_path / "subfolder"
    sub.mkdir()
    (sub / "photo3.png").write_text("fake")
    found = scan_photos(tmp_path)
    extensions = {p.suffix.lower() for p in found}
    assert len(found) == 3
    assert ".mp4" not in extensions
    assert ".txt" not in extensions
