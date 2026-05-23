"""Compute stage runners for the wizard server."""
import logging
import time
from pathlib import Path

from post_trip_summary.config import SessionConfig
from post_trip_summary.serialization import save_trip

logger = logging.getLogger("post_trip_summary.compute")


def _logging_callback(inner_callback=None):
    """Wrap a progress callback to also log to console."""
    last_phase = [None]
    phase_start = [time.time()]

    def _cb(phase, current, total, label=""):
        if phase != last_phase[0]:
            if last_phase[0] is not None:
                elapsed = time.time() - phase_start[0]
                logger.info("  Phase '%s' completed in %.1fs", last_phase[0], elapsed)
            last_phase[0] = phase
            phase_start[0] = time.time()
            logger.info("Phase: %s", phase)

        if total > 0:
            logger.debug("  [%d/%d] %s", current, total, label)
        elif label:
            logger.debug("  %s", label)

        if inner_callback:
            inner_callback(phase, current, total, label)

    return _cb


def run_ingest_pipeline(session: SessionConfig, progress_callback=None):
    """Run full ingest + skeleton pipeline with progress reporting."""
    start_time = time.time()
    logger.info("=== Starting ingest pipeline for '%s' ===", session.name)
    cb = _logging_callback(progress_callback)

    trip_data = _run_ingest(session, cb)
    logger.info("Ingest complete: %d photos, %d accommodations, %d expenses",
                len(trip_data["photos"]), len(trip_data["accommodations"]),
                len(trip_data["expenses"]))

    trip = _run_skeleton(session, trip_data, cb)
    total_events = sum(len(d.events) for d in trip.days)
    logger.info("Skeleton complete: %d days, %d events", len(trip.days), total_events)

    save_trip(trip, session.stage_file("ingested"))

    # Also save raw trip_data for debugging
    import json
    from post_trip_summary.serialization import encode_value
    raw_path = session.session_dir / "trip_data.json"
    raw_path.write_text(json.dumps(trip_data, default=encode_value, indent=2))

    elapsed = time.time() - start_time
    logger.info("=== Pipeline complete in %.1fs ===", elapsed)
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


def run_enrich_pipeline(session: SessionConfig, mode: str = "full", progress_callback=None):
    """Run enrichment pipeline with progress reporting."""
    start_time = time.time()
    logger.info("=== Starting enrichment (mode=%s) ===", mode)
    cb = _logging_callback(progress_callback)

    from post_trip_summary.serialization import load_trip
    trip = load_trip(session.stage_file("reviewed"))

    from post_trip_summary.pipeline.enrich import enrich_trip_headless
    trip = enrich_trip_headless(trip, mode=mode, progress_callback=cb)

    save_trip(trip, session.stage_file("enriched"))
    elapsed = time.time() - start_time
    logger.info("=== Enrichment complete in %.1fs ===", elapsed)
    return trip


def run_synthesis_pipeline(session: SessionConfig, progress_callback=None):
    """Run synthesis on highlight photos' descriptions. Text-only, fast."""
    start_time = time.time()
    logger.info("=== Starting synthesis ===")
    cb = _logging_callback(progress_callback)

    from post_trip_summary.serialization import load_trip
    # Load from enriched stage (highlights may have been adjusted)
    trip = load_trip(session.stage_file("enriched"))

    from post_trip_summary.pipeline.enrich import synthesize_event_descriptions
    trip = synthesize_event_descriptions(trip, progress_callback=cb)

    save_trip(trip, session.stage_file("highlights_done"))
    elapsed = time.time() - start_time
    logger.info("=== Synthesis complete in %.1fs ===", elapsed)
    return trip


def _run_skeleton(session, trip_data, progress_callback=None):
    from post_trip_summary.pipeline.skeleton import build_skeleton
    gap = session.settings.get("cluster_time_gap_minutes", 15)
    dist = session.settings.get("cluster_distance_meters", 200)
    trip = build_skeleton(
        trip_data,
        gap_minutes=gap,
        distance_meters=dist,
        progress_callback=progress_callback,
    )
    trip.name = session.name
    return trip
