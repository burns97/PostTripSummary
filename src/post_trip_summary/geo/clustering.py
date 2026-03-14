"""Photo clustering by time proximity and GPS proximity."""
from datetime import datetime, timedelta
from geopy.distance import geodesic

from post_trip_summary.models import Photo


def cluster_photos_by_time(photos: list[Photo], gap_minutes: int = 15) -> list[list[Photo]]:
    if not photos:
        return []
    sorted_photos = sorted(photos, key=lambda p: p.timestamp)
    groups = [[sorted_photos[0]]]
    for photo in sorted_photos[1:]:
        if photo.timestamp - groups[-1][-1].timestamp > timedelta(minutes=gap_minutes):
            groups.append([])
        groups[-1].append(photo)
    return groups


def cluster_by_gps(photos: list[Photo], distance_meters: int = 200) -> list[list[Photo]]:
    gps_photos = [p for p in photos if p.gps is not None]
    no_gps_photos = [p for p in photos if p.gps is None]
    if not gps_photos:
        return [photos] if photos else []
    clusters: list[list[Photo]] = [[gps_photos[0]]]
    for photo in gps_photos[1:]:
        merged = False
        for cluster in clusters:
            centroid = _centroid([p for p in cluster if p.gps])
            if centroid and geodesic(centroid, photo.gps).meters <= distance_meters:
                cluster.append(photo)
                merged = True
                break
        if not merged:
            clusters.append([photo])
    if no_gps_photos and clusters:
        clusters[0].extend(no_gps_photos)
    return clusters


def _centroid(photos: list[Photo]) -> tuple[float, float] | None:
    gps_points = [p.gps for p in photos if p.gps is not None]
    if not gps_points:
        return None
    avg_lat = sum(g[0] for g in gps_points) / len(gps_points)
    avg_lon = sum(g[1] for g in gps_points) / len(gps_points)
    return (avg_lat, avg_lon)


def build_clusters(photos: list[Photo], gap_minutes: int = 15, distance_meters: int = 200) -> list[dict]:
    time_groups = cluster_photos_by_time(photos, gap_minutes)
    clusters = []
    for group in time_groups:
        subclusters = cluster_by_gps(group, distance_meters)
        for subcluster in subclusters:
            sorted_sub = sorted(subcluster, key=lambda p: p.timestamp)
            centroid = _centroid(sorted_sub)
            clusters.append({"photos": sorted_sub, "centroid": centroid, "time_range": (sorted_sub[0].timestamp, sorted_sub[-1].timestamp)})
    return sorted(clusters, key=lambda c: c["time_range"][0])
