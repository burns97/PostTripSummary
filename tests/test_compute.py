from pathlib import Path
from datetime import datetime
from PIL import Image
from unittest.mock import patch
from post_trip_summary.config import create_session


def _create_test_photos(directory, count=3):
    for i in range(count):
        img_path = directory / f"IMG_{i:04d}.jpg"
        img = Image.new("RGB", (100, 100), color="blue")
        img.save(img_path, "JPEG")


def test_run_ingest_pipeline_with_progress(tmp_path):
    session = create_session("test-trip", base_dir=tmp_path)
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    _create_test_photos(photos_dir, count=3)
    session.inputs["photos"] = str(photos_dir)
    session.current_stage = "setup"
    session.save()

    progress_calls = []
    def mock_callback(phase, current, total, label=""):
        progress_calls.append((phase, current, total, label))

    from post_trip_summary.server.compute import run_ingest_pipeline

    mock_geo = {"name": "Test Place", "city": "Paris", "country": "France",
                "address": "123 Test St", "lat": 48.858, "lon": 2.294}
    with patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo):
        trip = run_ingest_pipeline(session, progress_callback=mock_callback)

    assert trip is not None
    assert trip.name == session.name
    assert len(trip.days) > 0
    phases = {call[0] for call in progress_calls}
    assert "scanning" in phases
    assert "scoring" in phases
    assert session.stage_file("ingested").exists()
