"""GPS interpolation for photos missing coordinates."""
from __future__ import annotations

from geopy.distance import geodesic

from post_trip_summary.models import Photo

# Safety caps
_MAX_TIME_GAP_SECONDS = 4 * 3600  # 4 hours
_MAX_DISTANCE_KM = 200
_MAX_DISTANCE_TIME_GAP_SECONDS = 30 * 60  # 30 minutes


def interpolate_missing_gps(photos: list[Photo]) -> None:
    """Fill in GPS for photos that lack it, using nearby timestamped photos.

    Mutates photos in place. Algorithm:
    - Sort by timestamp
    - For each photo with gps=None, find nearest GPS-tagged neighbors
    - Both neighbors: linear interpolation by time ratio (with safety caps)
    - One neighbor: copy its GPS
    - No neighbors: leave as None
    """
    if not photos:
        return

    sorted_photos = sorted(photos, key=lambda p: p.timestamp)

    # Build index of photos that have GPS
    gps_indices = [i for i, p in enumerate(sorted_photos) if p.gps is not None]
    if not gps_indices:
        return

    for i, photo in enumerate(sorted_photos):
        if photo.gps is not None:
            continue

        # Find nearest GPS neighbor before and after
        prev_idx = None
        next_idx = None
        for gi in gps_indices:
            if gi < i:
                prev_idx = gi
            elif gi > i:
                next_idx = gi
                break

        if prev_idx is not None and next_idx is not None:
            prev_photo = sorted_photos[prev_idx]
            next_photo = sorted_photos[next_idx]
            time_gap = (next_photo.timestamp - prev_photo.timestamp).total_seconds()

            if time_gap > _MAX_TIME_GAP_SECONDS:
                continue

            # Check distance cap for short time gaps
            dist_km = geodesic(prev_photo.gps, next_photo.gps).km
            if dist_km > _MAX_DISTANCE_KM and time_gap < _MAX_DISTANCE_TIME_GAP_SECONDS:
                continue

            # Linear interpolation by time ratio
            elapsed = (photo.timestamp - prev_photo.timestamp).total_seconds()
            ratio = elapsed / time_gap if time_gap > 0 else 0.5
            lat = prev_photo.gps[0] + ratio * (next_photo.gps[0] - prev_photo.gps[0])
            lon = prev_photo.gps[1] + ratio * (next_photo.gps[1] - prev_photo.gps[1])
            photo.gps = (lat, lon)

        elif prev_idx is not None:
            photo.gps = sorted_photos[prev_idx].gps

        elif next_idx is not None:
            photo.gps = sorted_photos[next_idx].gps
