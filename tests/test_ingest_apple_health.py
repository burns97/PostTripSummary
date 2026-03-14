# tests/test_ingest_apple_health.py
from datetime import datetime
from pathlib import Path
from post_trip_summary.pipeline.ingest.apple_health import ingest_apple_health


def _write_health_xml(path: Path) -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<HealthData>
 <Workout workoutActivityType="HKWorkoutActivityTypeWalking"
          duration="45.5"
          durationUnit="min"
          totalDistance="3.2"
          totalDistanceUnit="km"
          startDate="2026-03-05 16:00:00 +0000"
          endDate="2026-03-05 16:45:30 +0000">
  <WorkoutRoute>
   <Location date="2026-03-05 16:00:00 +0000" latitude="48.8584" longitude="2.2945" altitude="35.0"/>
   <Location date="2026-03-05 16:15:00 +0000" latitude="48.8600" longitude="2.2960" altitude="36.0"/>
   <Location date="2026-03-05 16:30:00 +0000" latitude="48.8620" longitude="2.2980" altitude="37.0"/>
  </WorkoutRoute>
 </Workout>
</HealthData>"""
    path.write_text(xml, encoding="utf-8")


def test_parse_workout(tmp_path):
    xml_path = tmp_path / "export.xml"
    _write_health_xml(xml_path)
    result = ingest_apple_health(xml_path)
    assert len(result) == 1
    workout = result[0]
    assert workout["activity_type"] == "walking"
    assert workout["duration_minutes"] == 45.5
    assert workout["distance_km"] == 3.2


def test_parse_workout_route(tmp_path):
    xml_path = tmp_path / "export.xml"
    _write_health_xml(xml_path)
    result = ingest_apple_health(xml_path)
    workout = result[0]
    assert len(workout["route"]) == 3
    assert abs(workout["route"][0]["lat"] - 48.8584) < 0.001


def test_empty_health_data(tmp_path):
    xml_path = tmp_path / "empty.xml"
    xml_path.write_text('<?xml version="1.0"?><HealthData></HealthData>', encoding="utf-8")
    result = ingest_apple_health(xml_path)
    assert result == []
