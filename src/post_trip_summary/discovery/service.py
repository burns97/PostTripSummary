"""Session-level Vacation Blend discovery orchestration."""
from __future__ import annotations

from post_trip_summary.config import SessionConfig
from post_trip_summary.discovery.metadata import discover_vacation_blend
from post_trip_summary.discovery.models import VacationBlend
from post_trip_summary.discovery.serialization import (
    save_vacation_blend,
    vacation_blend_path,
)
from post_trip_summary.serialization import load_trip


def run_discovery_for_session(
    session: SessionConfig,
    advance_stage: bool = True,
) -> VacationBlend:
    reviewed_path = session.stage_file("reviewed")
    if not reviewed_path.exists():
        raise FileNotFoundError(
            f"Reviewed trip file not found for session '{session.slug}': {reviewed_path}"
        )

    trip = load_trip(reviewed_path)
    blend = discover_vacation_blend(trip)
    save_vacation_blend(vacation_blend_path(session.session_dir), blend)

    if advance_stage and session.current_stage == "reviewed":
        session.current_stage = "discovered"
        session.save()

    return blend
