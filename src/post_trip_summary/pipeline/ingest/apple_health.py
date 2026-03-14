# src/post_trip_summary/pipeline/ingest/apple_health.py
"""Parse Apple Health XML export for workout routes."""
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

_ACTIVITY_MAP = {
    "HKWorkoutActivityTypeWalking": "walking",
    "HKWorkoutActivityTypeRunning": "running",
    "HKWorkoutActivityTypeHiking": "hiking",
    "HKWorkoutActivityTypeCycling": "cycling",
}

_DATE_FMT = "%Y-%m-%d %H:%M:%S %z"


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, _DATE_FMT).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def ingest_apple_health(path: Path) -> list[dict]:
    tree = ET.parse(path)
    root = tree.getroot()
    workouts = []
    for workout_elem in root.iter("Workout"):
        activity_raw = workout_elem.get("workoutActivityType", "")
        activity = _ACTIVITY_MAP.get(activity_raw, activity_raw.replace("HKWorkoutActivityType", "").lower())
        start = _parse_date(workout_elem.get("startDate", ""))
        end = _parse_date(workout_elem.get("endDate", ""))
        try:
            duration = float(workout_elem.get("duration", 0))
        except (ValueError, TypeError):
            duration = 0.0
        try:
            distance = float(workout_elem.get("totalDistance", 0))
        except (ValueError, TypeError):
            distance = 0.0
        route = []
        for route_elem in workout_elem.iter("WorkoutRoute"):
            for loc_elem in route_elem.iter("Location"):
                try:
                    route.append({
                        "lat": float(loc_elem.get("latitude", 0)),
                        "lon": float(loc_elem.get("longitude", 0)),
                        "altitude": float(loc_elem.get("altitude", 0)),
                        "timestamp": _parse_date(loc_elem.get("date", "")),
                    })
                except (ValueError, TypeError):
                    continue
        workouts.append({
            "activity_type": activity, "start": start, "end": end,
            "duration_minutes": duration, "distance_km": distance,
            "route": route, "source": "apple_health",
        })
    return workouts
