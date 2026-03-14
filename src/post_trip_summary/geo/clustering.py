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


def build_clusters(photos: list[Photo], gap_minutes: int = 30, distance_meters: int = 500) -> list[dict]:
    time_groups = cluster_photos_by_time(photos, gap_minutes)
    clusters = []
    for group in time_groups:
        subclusters = cluster_by_gps(group, distance_meters)
        for subcluster in subclusters:
            sorted_sub = sorted(subcluster, key=lambda p: p.timestamp)
            centroid = _centroid(sorted_sub)
            clusters.append({"photos": sorted_sub, "centroid": centroid, "time_range": (sorted_sub[0].timestamp, sorted_sub[-1].timestamp)})
    return sorted(clusters, key=lambda c: c["time_range"][0])


def _merge_two_clusters(a: dict, b: dict) -> dict:
    """Merge two cluster dicts into one."""
    photos = sorted(a["photos"] + b["photos"], key=lambda p: p.timestamp)
    centroid = _centroid(photos)
    time_range = (
        min(a["time_range"][0], b["time_range"][0]),
        max(a["time_range"][1], b["time_range"][1]),
    )
    merged = {"photos": photos, "centroid": centroid, "time_range": time_range}
    # Propagate transit_hint only if both had it
    if a.get("transit_hint") and b.get("transit_hint"):
        merged["transit_hint"] = True
    return merged


def merge_nearby_clusters(
    clusters: list[dict],
    merge_radius_m: float = 1000,
    merge_max_gap_minutes: float = 120,
    merge_max_span_hours: float = 6,
) -> list[dict]:
    """Merge adjacent clusters that are geographically close and temporally near."""
    if len(clusters) <= 1:
        return list(clusters)

    changed = True
    result = list(clusters)
    while changed:
        changed = False
        merged = []
        i = 0
        while i < len(result):
            if i + 1 < len(result):
                a, b = result[i], result[i + 1]
                # Check centroids exist
                if a["centroid"] and b["centroid"]:
                    dist = geodesic(a["centroid"], b["centroid"]).meters
                    gap = (b["time_range"][0] - a["time_range"][1]).total_seconds() / 60
                    combined_start = min(a["time_range"][0], b["time_range"][0])
                    combined_end = max(a["time_range"][1], b["time_range"][1])
                    span_hours = (combined_end - combined_start).total_seconds() / 3600

                    if dist <= merge_radius_m and gap <= merge_max_gap_minutes and span_hours <= merge_max_span_hours:
                        merged.append(_merge_two_clusters(a, b))
                        i += 2
                        changed = True
                        continue
            merged.append(result[i])
            i += 1
        result = merged

    return result


def detect_and_collapse_transit(
    clusters: list[dict],
    transit_max_photos: int = 3,
    transit_min_speed_kmh: float = 20,
    min_run_length: int = 3,
) -> list[dict]:
    """Detect runs of small clusters at high speed and collapse them into transit events."""
    if len(clusters) < min_run_length:
        return list(clusters)

    # Find candidate transit clusters (small, with GPS)
    candidates = []
    for i, c in enumerate(clusters):
        if len(c["photos"]) <= transit_max_photos and c["centroid"] is not None:
            candidates.append(i)

    # Find runs of consecutive candidate indices
    runs: list[list[int]] = []
    current_run: list[int] = []
    for idx in candidates:
        if not current_run or idx == current_run[-1] + 1:
            current_run.append(idx)
        else:
            if len(current_run) >= min_run_length:
                runs.append(current_run)
            current_run = [idx]
    if len(current_run) >= min_run_length:
        runs.append(current_run)

    # Validate speed for each run
    valid_runs: list[list[int]] = []
    for run in runs:
        speeds = []
        for j in range(len(run) - 1):
            a, b = clusters[run[j]], clusters[run[j + 1]]
            dist_km = geodesic(a["centroid"], b["centroid"]).km
            time_hours = (b["time_range"][0] - a["time_range"][1]).total_seconds() / 3600
            if time_hours <= 0:
                # Use midpoints if gap is zero
                a_mid = a["time_range"][0] + (a["time_range"][1] - a["time_range"][0]) / 2
                b_mid = b["time_range"][0] + (b["time_range"][1] - b["time_range"][0]) / 2
                time_hours = (b_mid - a_mid).total_seconds() / 3600
            if time_hours > 0:
                speeds.append(dist_km / time_hours)
        if speeds and (sum(speeds) / len(speeds)) >= transit_min_speed_kmh:
            valid_runs.append(run)

    # Collapse valid runs
    collapse_indices: set[int] = set()
    collapsed_clusters: dict[int, dict] = {}  # keyed by first index in run
    for run in valid_runs:
        for idx in run:
            collapse_indices.add(idx)
        merged = clusters[run[0]]
        for idx in run[1:]:
            merged = _merge_two_clusters(merged, clusters[idx])
        merged["transit_hint"] = True
        collapsed_clusters[run[0]] = merged

    result = []
    for i, c in enumerate(clusters):
        if i in collapse_indices:
            if i in collapsed_clusters:
                result.append(collapsed_clusters[i])
        else:
            result.append(c)

    return result
