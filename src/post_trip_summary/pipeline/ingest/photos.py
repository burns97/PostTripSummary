# src/post_trip_summary/pipeline/ingest/photos.py
"""EXIF extraction and photo scanning using Pillow."""
import re
from datetime import datetime
from pathlib import Path

from PIL import Image
from PIL.ExifTags import Base as ExifBase, GPS as GPSTags

from post_trip_summary.models import Photo

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".webp"}

_EXIF_DATE_FMT = "%Y:%m:%d %H:%M:%S"
_FILENAME_PATTERN = re.compile(r"IMG_(\d{8})_(\d{6})")


def scan_photos(directory: Path) -> list[Path]:
    photos = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            photos.append(path)
    return photos


def _parse_exif_date(value) -> datetime | None:
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


def _dms_to_decimal(dms_tuple, ref: str) -> float | None:
    """Convert GPS DMS (degrees, minutes, seconds) to decimal degrees."""
    try:
        degrees = float(dms_tuple[0])
        minutes = float(dms_tuple[1])
        seconds = float(dms_tuple[2])
        decimal = degrees + minutes / 60 + seconds / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except (TypeError, ValueError, IndexError):
        return None


def _extract_timestamp_from_exif(exif_dict: dict) -> datetime | None:
    """Try DateTimeOriginal, then DateTimeDigitized, then DateTime."""
    for tag_id in (ExifBase.DateTimeOriginal, ExifBase.DateTimeDigitized, ExifBase.DateTime):
        value = exif_dict.get(tag_id)
        dt = _parse_exif_date(value)
        if dt:
            return dt
    return None


def _extract_gps_from_exif(exif_dict: dict) -> tuple[float, float] | None:
    """Extract GPS coordinates from Pillow's GPSInfo dict."""
    gps_info = exif_dict.get(ExifBase.GPSInfo)
    if not isinstance(gps_info, dict):
        return None

    lat_dms = gps_info.get(GPSTags.GPSLatitude)
    lat_ref = gps_info.get(GPSTags.GPSLatitudeRef, "N")
    lon_dms = gps_info.get(GPSTags.GPSLongitude)
    lon_ref = gps_info.get(GPSTags.GPSLongitudeRef, "E")

    if lat_dms is None or lon_dms is None:
        return None

    lat = _dms_to_decimal(lat_dms, lat_ref)
    lon = _dms_to_decimal(lon_dms, lon_ref)
    if lat is None or lon is None:
        return None
    return (lat, lon)


def extract_photo_metadata(path: Path) -> Photo:
    """Read EXIF from an image file using Pillow and return a Photo."""
    timestamp = None
    gps = None
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                timestamp = _extract_timestamp_from_exif(exif)
                # GPSInfo is an IFD that needs explicit loading
                gps_ifd = exif.get_ifd(ExifBase.GPSInfo)
                if gps_ifd:
                    exif[ExifBase.GPSInfo] = gps_ifd
                gps = _extract_gps_from_exif(exif)
    except Exception:
        pass

    if timestamp is None:
        timestamp = _parse_filename_date(path)

    return Photo(path=path, timestamp=timestamp or datetime.min, gps=gps)


def ingest_photos(directory: Path, progress_callback=None) -> list[Photo]:
    # Register HEIF/HEIC opener if available
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass

    paths = scan_photos(directory)
    if not paths:
        return []
    photos = []
    for i, p in enumerate(paths):
        photos.append(extract_photo_metadata(p))
        if progress_callback:
            progress_callback("scanning", i + 1, len(paths), p.name)
    return sorted(photos, key=lambda p: p.timestamp)
