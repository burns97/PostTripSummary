# tests/test_ingest_photos.py
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.ExifTags import Base as ExifBase, GPS as GPSTags

from post_trip_summary.pipeline.ingest.photos import (
    scan_photos,
    extract_photo_metadata,
    _parse_exif_date,
    _parse_filename_date,
    _dms_to_decimal,
    _extract_timestamp_from_exif,
    _extract_gps_from_exif,
    SUPPORTED_EXTENSIONS,
)


def _make_jpeg(path: Path, exif_dict: dict | None = None, gps_dict: dict | None = None):
    """Create a minimal JPEG with optional EXIF data."""
    img = Image.new("RGB", (1, 1), color="red")
    exif = img.getexif()
    if exif_dict:
        for k, v in exif_dict.items():
            exif[k] = v
    if gps_dict:
        exif[ExifBase.GPSInfo] = gps_dict
    img.save(path, exif=exif)


# --- Pure function tests (no files needed) ---

def test_supported_extensions():
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".heic" in SUPPORTED_EXTENSIONS
    assert ".mp4" not in SUPPORTED_EXTENSIONS


def test_parse_exif_date():
    assert _parse_exif_date("2026:03:05 16:30:00") == datetime(2026, 3, 5, 16, 30, 0)
    assert _parse_exif_date("") is None
    assert _parse_exif_date(None) is None
    assert _parse_exif_date("not a date") is None


def test_parse_filename_date():
    assert _parse_filename_date(Path("IMG_20260305_163000.jpg")) == datetime(2026, 3, 5, 16, 30, 0)
    assert _parse_filename_date(Path("photo.jpg")) is None


def test_dms_to_decimal_north_east():
    lat = _dms_to_decimal((48.0, 51.0, 30.24), "N")
    assert abs(lat - 48.8584) < 0.001


def test_dms_to_decimal_south_west():
    lat = _dms_to_decimal((37.0, 46.0, 29.64), "S")
    assert lat < 0
    lon = _dms_to_decimal((122.0, 25.0, 9.84), "W")
    assert lon < 0


def test_extract_timestamp_from_exif():
    exif = {ExifBase.DateTimeOriginal: "2026:03:05 16:30:00"}
    assert _extract_timestamp_from_exif(exif) == datetime(2026, 3, 5, 16, 30, 0)

    exif2 = {ExifBase.DateTimeDigitized: "2026:03:05 17:00:00"}
    assert _extract_timestamp_from_exif(exif2) == datetime(2026, 3, 5, 17, 0, 0)

    assert _extract_timestamp_from_exif({}) is None


def test_extract_gps_from_exif():
    exif = {
        ExifBase.GPSInfo: {
            GPSTags.GPSLatitude: (48.0, 51.0, 30.24),
            GPSTags.GPSLatitudeRef: "N",
            GPSTags.GPSLongitude: (2.0, 17.0, 40.2),
            GPSTags.GPSLongitudeRef: "E",
        }
    }
    gps = _extract_gps_from_exif(exif)
    assert gps is not None
    assert abs(gps[0] - 48.8584) < 0.001
    assert abs(gps[1] - 2.2945) < 0.001


def test_extract_gps_from_exif_missing():
    assert _extract_gps_from_exif({}) is None
    assert _extract_gps_from_exif({ExifBase.GPSInfo: "not a dict"}) is None


# --- Integration tests using real image files ---

def test_extract_metadata_with_exif(tmp_path):
    path = tmp_path / "photo.jpg"
    _make_jpeg(path, exif_dict={ExifBase.DateTimeOriginal: "2026:03:05 16:30:00"})
    result = extract_photo_metadata(path)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)


def test_extract_metadata_with_gps(tmp_path):
    path = tmp_path / "photo.jpg"
    _make_jpeg(
        path,
        exif_dict={ExifBase.DateTimeOriginal: "2026:03:05 16:30:00"},
        gps_dict={
            GPSTags.GPSLatitude: (48.0, 51.0, 30.24),
            GPSTags.GPSLatitudeRef: "N",
            GPSTags.GPSLongitude: (2.0, 17.0, 40.2),
            GPSTags.GPSLongitudeRef: "E",
        },
    )
    result = extract_photo_metadata(path)
    assert result.gps is not None
    assert abs(result.gps[0] - 48.8584) < 0.001
    assert abs(result.gps[1] - 2.2945) < 0.001


def test_extract_metadata_no_exif(tmp_path):
    path = tmp_path / "photo.jpg"
    _make_jpeg(path)
    result = extract_photo_metadata(path)
    assert result.timestamp == datetime.min
    assert result.gps is None


def test_extract_metadata_filename_fallback(tmp_path):
    path = tmp_path / "IMG_20260305_163000.jpg"
    _make_jpeg(path)
    result = extract_photo_metadata(path)
    assert result.timestamp == datetime(2026, 3, 5, 16, 30, 0)


def test_extract_metadata_south_west_gps(tmp_path):
    path = tmp_path / "photo.jpg"
    _make_jpeg(
        path,
        exif_dict={ExifBase.DateTimeOriginal: "2026:03:05 10:00:00"},
        gps_dict={
            GPSTags.GPSLatitude: (37.0, 46.0, 29.64),
            GPSTags.GPSLatitudeRef: "S",
            GPSTags.GPSLongitude: (122.0, 25.0, 9.84),
            GPSTags.GPSLongitudeRef: "W",
        },
    )
    result = extract_photo_metadata(path)
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
