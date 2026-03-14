# src/post_trip_summary/pipeline/ingest/photos.py
"""EXIF extraction and photo scanning."""
import re
from datetime import datetime
from pathlib import Path

from post_trip_summary.models import Photo

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".webp"}

_DATE_TAGS = [
    "EXIF:DateTimeOriginal",
    "RIFF:DateTimeOriginal",
    "QuickTime:CreateDate",
    "Composite:GPSDateTime",
    "EXIF:CreateDate",
]

_EXIF_DATE_FMT = "%Y:%m:%d %H:%M:%S"
_FILENAME_PATTERN = re.compile(r"IMG_(\d{8})_(\d{6})")


def scan_photos(directory: Path) -> list[Path]:
    photos = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            photos.append(path)
    return photos


def _parse_exif_date(value: str) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), _EXIF_DATE_FMT)
    except (ValueError, TypeError):
        return None


def _parse_filename_date(path: Path) -> datetime | None:
    match = _FILENAME_PATTERN.search(path.stem)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)}_{match.group(2)}", "%Y%m%d_%H%M%S")
        except ValueError:
            return None
    return None


def _extract_timestamp(path: Path, tags: dict) -> datetime | None:
    for tag in _DATE_TAGS:
        if tag in tags:
            dt = _parse_exif_date(tags[tag])
            if dt:
                return dt
    return _parse_filename_date(path)


def _extract_gps(tags: dict) -> tuple[float, float] | None:
    lat = tags.get("EXIF:GPSLatitude")
    lon = tags.get("EXIF:GPSLongitude")
    if lat is None or lon is None:
        return None
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return None
    lat_ref = tags.get("EXIF:GPSLatitudeRef", "N")
    lon_ref = tags.get("EXIF:GPSLongitudeRef", "E")
    if lat_ref == "S":
        lat = -abs(lat)
    if lon_ref == "W":
        lon = -abs(lon)
    return (lat, lon)


def extract_photo_metadata(path: Path, tags: dict) -> Photo:
    timestamp = _extract_timestamp(path, tags)
    gps = _extract_gps(tags)
    return Photo(path=path, timestamp=timestamp or datetime.min, gps=gps)


def ingest_photos(directory: Path) -> list[Photo]:
    import exiftool
    paths = scan_photos(directory)
    if not paths:
        return []
    photos = []
    batch_size = 50
    with exiftool.ExifToolHelper() as et:
        for i in range(0, len(paths), batch_size):
            batch = paths[i : i + batch_size]
            str_paths = [str(p) for p in batch]
            all_tags = et.get_tags(str_paths, _DATE_TAGS + [
                "EXIF:GPSLatitude", "EXIF:GPSLongitude",
                "EXIF:GPSLatitudeRef", "EXIF:GPSLongitudeRef",
            ])
            for path, tags in zip(batch, all_tags):
                photos.append(extract_photo_metadata(path, tags))
    return sorted(photos, key=lambda p: p.timestamp)
