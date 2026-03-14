# tests/test_clustering.py
from datetime import datetime
from pathlib import Path
from post_trip_summary.models import Photo
from post_trip_summary.geo.clustering import cluster_photos_by_time, cluster_by_gps, build_clusters


def _photo(ts: str, lat: float = 48.858, lon: float = 2.294) -> Photo:
    return Photo(path=Path(f"/photos/{ts.replace(' ', '_').replace(':', '')}.jpg"), timestamp=datetime.fromisoformat(ts), gps=(lat, lon))


def _photo_no_gps(ts: str) -> Photo:
    return Photo(path=Path(f"/photos/{ts.replace(' ', '_')}.jpg"), timestamp=datetime.fromisoformat(ts), gps=None)


def test_time_clustering_single_group():
    photos = [_photo("2026-03-05 16:00:00"), _photo("2026-03-05 16:05:00"), _photo("2026-03-05 16:10:00")]
    groups = cluster_photos_by_time(photos, gap_minutes=15)
    assert len(groups) == 1
    assert len(groups[0]) == 3


def test_time_clustering_two_groups():
    photos = [_photo("2026-03-05 16:00:00"), _photo("2026-03-05 16:05:00"), _photo("2026-03-05 17:00:00"), _photo("2026-03-05 17:05:00")]
    groups = cluster_photos_by_time(photos, gap_minutes=15)
    assert len(groups) == 2
    assert len(groups[0]) == 2
    assert len(groups[1]) == 2


def test_gps_subclustering():
    photos = [_photo("2026-03-05 16:00:00", lat=48.858, lon=2.294), _photo("2026-03-05 16:05:00", lat=48.858, lon=2.295), _photo("2026-03-05 16:10:00", lat=48.886, lon=2.343)]
    subclusters = cluster_by_gps(photos, distance_meters=200)
    assert len(subclusters) == 2


def test_build_clusters_full_pipeline():
    photos = [_photo("2026-03-05 10:00:00", lat=48.858, lon=2.294), _photo("2026-03-05 10:05:00", lat=48.858, lon=2.295), _photo("2026-03-05 12:00:00", lat=48.860, lon=2.336), _photo("2026-03-05 12:10:00", lat=48.861, lon=2.337)]
    clusters = build_clusters(photos, gap_minutes=15, distance_meters=200)
    assert len(clusters) == 2
    for cluster in clusters:
        assert "photos" in cluster
        assert "centroid" in cluster
        assert "time_range" in cluster


def test_cluster_centroid():
    photos = [_photo("2026-03-05 16:00:00", lat=48.0, lon=2.0), _photo("2026-03-05 16:05:00", lat=49.0, lon=3.0)]
    clusters = build_clusters(photos, gap_minutes=15, distance_meters=150000)
    assert len(clusters) == 1
    centroid = clusters[0]["centroid"]
    assert abs(centroid[0] - 48.5) < 0.01
    assert abs(centroid[1] - 2.5) < 0.01


def test_photos_without_gps():
    photos = [_photo_no_gps("2026-03-05 16:00:00"), _photo_no_gps("2026-03-05 16:05:00")]
    clusters = build_clusters(photos, gap_minutes=15, distance_meters=200)
    assert len(clusters) == 1
    assert clusters[0]["centroid"] is None
