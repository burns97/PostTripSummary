"""Compute stage runners for the wizard server."""
from pathlib import Path

from post_trip_summary.config import SessionConfig
from post_trip_summary.serialization import save_trip


def run_ingest_pipeline(session: SessionConfig, progress_callback=None):
    """Run full ingest + skeleton pipeline with progress reporting."""
    trip_data = _run_ingest(session, progress_callback)
    trip = _run_skeleton(session, trip_data, progress_callback)
    save_trip(trip, session.stage_file("ingested"))

    # Also save raw trip_data for debugging
    import json
    from post_trip_summary.serialization import encode_value
    raw_path = session.session_dir / "trip_data.json"
    raw_path.write_text(json.dumps(trip_data, default=encode_value, indent=2))

    return trip


def _run_ingest(session, progress_callback=None):
    trip_data = {
        "photos": [], "accommodations": [], "transits": [],
        "activities": [], "expenses": [],
        "google_maps": {}, "apple_health": [], "dayone": [],
    }
    inputs = session.inputs

    photos_path = inputs.get("photos")
    if photos_path:
        from post_trip_summary.pipeline.ingest.photos import ingest_photos
        trip_data["photos"] = ingest_photos(Path(photos_path), progress_callback=progress_callback)

    excel_path = inputs.get("excel")
    if excel_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing Excel itinerary...")
        from post_trip_summary.pipeline.ingest.excel import ingest_excel
        excel_data = ingest_excel(Path(excel_path))
        trip_data["accommodations"] = excel_data.get("accommodations", [])
        trip_data["transits"] = excel_data.get("transits", [])
        trip_data["activities"] = excel_data.get("activities", [])
        trip_data["expenses"].extend(excel_data.get("expenses", []))

    cc_path = inputs.get("credit_card")
    if cc_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing credit card CSV...")
        from post_trip_summary.pipeline.ingest.credit_card import ingest_credit_card
        trip_data["expenses"].extend(ingest_credit_card(Path(cc_path)))

    maps_path = inputs.get("google_maps")
    if maps_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing Google Maps timeline...")
        from post_trip_summary.pipeline.ingest.google_maps import ingest_google_maps
        trip_data["google_maps"] = ingest_google_maps(Path(maps_path))

    health_path = inputs.get("apple_health")
    if health_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing Apple Health data...")
        from post_trip_summary.pipeline.ingest.apple_health import ingest_apple_health
        trip_data["apple_health"] = ingest_apple_health(Path(health_path))

    dayone_path = inputs.get("dayone")
    if dayone_path:
        if progress_callback:
            progress_callback("supplementary", 0, 0, "Parsing Day One journal...")
        from post_trip_summary.pipeline.ingest.dayone import ingest_dayone
        trip_data["dayone"] = ingest_dayone(Path(dayone_path))

    # Quality scoring
    if trip_data["photos"]:
        from post_trip_summary.pipeline.quality import score_photos, apply_quality_cull
        score_photos(trip_data["photos"], progress_callback=progress_callback)
        cull_pct = session.settings.get("quality_cull_percentile", 15)
        culled = apply_quality_cull(trip_data["photos"], percentile=cull_pct)
        if progress_callback:
            progress_callback("scoring", len(trip_data["photos"]), len(trip_data["photos"]),
                            f"Culled {culled} low-quality photos")

    return trip_data


def _run_skeleton(session, trip_data, progress_callback=None):
    from post_trip_summary.pipeline.skeleton import build_skeleton
    gap = session.settings.get("cluster_time_gap_minutes", 15)
    dist = session.settings.get("cluster_distance_meters", 200)
    return build_skeleton(trip_data, gap_minutes=gap, distance_meters=dist,
                         progress_callback=progress_callback)
