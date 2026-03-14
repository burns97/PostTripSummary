# tests/test_clustering.py
from datetime import datetime, timedelta
from pathlib import Path
from post_trip_summary.models import Photo
from post_trip_summary.geo.clustering import (
    cluster_photos_by_time,
    cluster_by_gps,
    build_clusters,
    merge_nearby_clusters,
    detect_and_collapse_transit,
)


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


# --- merge_nearby_clusters tests ---


def _make_cluster(ts_str: str, lat: float, lon: float, num_photos: int = 2) -> dict:
    """Helper to build a cluster dict for merge/transit tests."""
    base = datetime.fromisoformat(ts_str)
    photos = [
        Photo(path=Path(f"/p/{ts_str}_{i}.jpg"), timestamp=base + timedelta(minutes=i), gps=(lat, lon))
        for i in range(num_photos)
    ]
    return {
        "photos": photos,
        "centroid": (lat, lon),
        "time_range": (photos[0].timestamp, photos[-1].timestamp),
    }


def test_merge_same_area_clusters():
    """5 clusters within 500m and 10min apart should merge to 1."""
    clusters = [
        _make_cluster("2026-03-05 10:00:00", -36.8485, 174.7633),
        _make_cluster("2026-03-05 10:10:00", -36.8490, 174.7640),
        _make_cluster("2026-03-05 10:20:00", -36.8480, 174.7630),
        _make_cluster("2026-03-05 10:30:00", -36.8488, 174.7635),
        _make_cluster("2026-03-05 10:40:00", -36.8483, 174.7638),
    ]
    result = merge_nearby_clusters(clusters, merge_radius_m=1000, merge_max_gap_minutes=120)
    assert len(result) == 1
    assert len(result[0]["photos"]) == 10


def test_merge_respects_max_span():
    """2 clusters 8 hours apart at the same location should stay separate."""
    clusters = [
        _make_cluster("2026-03-05 08:00:00", -36.8485, 174.7633),
        _make_cluster("2026-03-05 16:00:00", -36.8485, 174.7633),
    ]
    result = merge_nearby_clusters(clusters, merge_radius_m=1000, merge_max_gap_minutes=120, merge_max_span_hours=6)
    assert len(result) == 2


def test_merge_respects_distance():
    """Clusters far apart should not merge even if temporally close."""
    clusters = [
        _make_cluster("2026-03-05 10:00:00", -36.8485, 174.7633),  # Auckland
        _make_cluster("2026-03-05 10:30:00", -37.7870, 175.2793),  # Hamilton
    ]
    result = merge_nearby_clusters(clusters, merge_radius_m=1000, merge_max_gap_minutes=120)
    assert len(result) == 2


# --- detect_and_collapse_transit tests ---


def test_transit_detection():
    """6 single-photo clusters along a highway at ~80km/h should collapse to 1."""
    # Points roughly along Auckland-Hamilton highway, ~15min apart
    points = [
        ("2026-03-05 10:00:00", -36.85, 174.76),   # Auckland
        ("2026-03-05 10:15:00", -36.98, 174.88),    # South Auckland
        ("2026-03-05 10:30:00", -37.15, 175.00),    # Papakura area
        ("2026-03-05 10:45:00", -37.35, 175.15),    # Huntly area
        ("2026-03-05 11:00:00", -37.55, 175.22),    # Ngaruawahia
        ("2026-03-05 11:15:00", -37.78, 175.28),    # Hamilton
    ]
    clusters = [_make_cluster(ts, lat, lon, num_photos=1) for ts, lat, lon in points]
    result = detect_and_collapse_transit(clusters, transit_max_photos=3, transit_min_speed_kmh=20, min_run_length=3)
    assert len(result) == 1
    assert result[0].get("transit_hint") is True
    assert len(result[0]["photos"]) == 6


def test_transit_does_not_collapse_stationary():
    """Clusters at the same spot should not be detected as transit."""
    clusters = [
        _make_cluster(f"2026-03-05 10:{i*10:02d}:00", -36.85, 174.76, num_photos=1)
        for i in range(5)
    ]
    result = detect_and_collapse_transit(clusters, transit_max_photos=3, transit_min_speed_kmh=20, min_run_length=3)
    # Should remain uncollapsed since speed is ~0
    assert len(result) == 5


def test_driving_day_scenario():
    """Synthetic Auckland -> Hamilton -> Rotorua day should produce ~5-6 clusters."""
    base = datetime.fromisoformat("2026-03-05 08:00:00")

    def _photos(start_offset_min, lat, lon, count, gap_min=5):
        return [
            Photo(
                path=Path(f"/p/{start_offset_min}_{i}.jpg"),
                timestamp=base + timedelta(minutes=start_offset_min + i * gap_min),
                gps=(lat, lon),
            )
            for i in range(count)
        ]

    photos = []
    # Auckland morning: 8:00-8:40 (9 photos at Auckland spots)
    photos.extend(_photos(0, -36.8485, 174.7633, 5))
    photos.extend(_photos(25, -36.8520, 174.7670, 4))

    # Drive Auckland -> Hamilton: roadside photos 9:00 - 10:30
    drive1_points = [
        (60, -36.95, 174.85),
        (75, -37.10, 174.95),
        (90, -37.30, 175.10),
        (105, -37.50, 175.20),
        (120, -37.65, 175.25),
    ]
    for offset, lat, lon in drive1_points:
        photos.extend(_photos(offset, lat, lon, 1))

    # Hamilton stop: 10:30-11:30 (8 photos)
    photos.extend(_photos(150, -37.7870, 175.2793, 4))
    photos.extend(_photos(175, -37.7900, 175.2830, 4))

    # Drive Hamilton -> Rotorua: 12:00 - 13:00
    drive2_points = [
        (240, -37.90, 175.50),
        (252, -38.05, 175.70),
        (264, -38.20, 175.90),
        (276, -38.30, 176.10),
    ]
    for offset, lat, lon in drive2_points:
        photos.extend(_photos(offset, lat, lon, 1))

    # Rotorua afternoon: 13:30 - 16:00 (12 photos at various spots)
    photos.extend(_photos(330, -38.1368, 176.2497, 4))
    photos.extend(_photos(360, -38.1400, 176.2530, 4))
    photos.extend(_photos(420, -38.1580, 176.2510, 4))

    # Run full pipeline
    clusters = build_clusters(photos, gap_minutes=30, distance_meters=500)
    clusters = merge_nearby_clusters(clusters)
    clusters = detect_and_collapse_transit(clusters)

    # Should produce roughly 4-7 clusters: Auckland, transit1, Hamilton, transit2, Rotorua (1-2)
    assert 3 <= len(clusters) <= 7, f"Expected 3-7 clusters, got {len(clusters)}"

    # Verify transit hints exist
    transit_clusters = [c for c in clusters if c.get("transit_hint")]
    assert len(transit_clusters) >= 1, "Expected at least one transit cluster"
