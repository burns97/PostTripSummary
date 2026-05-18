from datetime import date, datetime, timedelta
from pathlib import Path

from post_trip_summary.discovery.metadata import discover_vacation_blend
from post_trip_summary.models import Day, Event, Location, Photo, Trip


def _photo(event_id: str, index: int, timestamp: datetime, lat: float, lon: float) -> Photo:
    return Photo(
        path=Path(f"{event_id}-{index}.jpg"),
        timestamp=timestamp + timedelta(minutes=index),
        gps=(lat, lon),
    )


def _event(
    event_id: str,
    name: str,
    city: str,
    country: str,
    lat: float,
    lon: float,
    hour: int = 10,
    event_type: str = "activity",
    photo_count: int = 3,
    description: str = "",
) -> Event:
    day_offset = int(event_id.split("-")[-1]) if "-" in event_id else 0
    start = datetime(2026, 1, 1, hour, 0) + timedelta(days=day_offset)
    return Event(
        id=event_id,
        type=event_type,
        name=name,
        time_range=(start, start + timedelta(hours=1)),
        location=Location(
            lat=lat,
            lon=lon,
            name=name,
            address=f"{name}, {city}",
            city=city,
            country=country,
        ),
        photos=[
            _photo(event_id, index, start, lat + index * 0.001, lon + index * 0.001)
            for index in range(photo_count)
        ],
        description=description,
    )


def _trip(events_by_day: list[list[Event]]) -> Trip:
    start = date(2026, 1, 1)
    days = [
        Day(date=start + timedelta(days=index), events=events)
        for index, events in enumerate(events_by_day)
    ]
    return Trip(name="Test Trip", date_range=(days[0].date, days[-1].date), days=days)


def _primary_ids(blend):
    return [score.theme_id for score in blend.primary]


def _detected_ids(blend):
    return {score.theme_id for score in blend.primary + blend.secondary}


def test_new_zealand_hiking_scenic_trip_detects_road_trip_and_adventure_primary():
    trip = _trip(
        [
            [
                _event("nz-0", "Scenic highway drive to Lake Tekapo viewpoint", "Tekapo", "New Zealand", -44.0, 170.4),
                _event("nz-1", "Alpine hiking trail", "Aoraki", "New Zealand", -43.6, 170.1),
            ],
            [
                _event("nz-2", "Glacier lake walk and mountain lookout", "Wanaka", "New Zealand", -44.7, 169.1),
            ],
            [
                _event("nz-3", "Fjord boat adventure", "Te Anau", "New Zealand", -45.4, 167.7),
            ],
        ]
    )

    blend = discover_vacation_blend(trip)

    assert blend.analysis_mode == "metadata_only"
    assert "road_trip" in _primary_ids(blend)
    assert "adventure_outdoors" in _primary_ids(blend)
    evidence = " ".join(
        reason
        for score in blend.primary
        if score.theme_id in {"road_trip", "adventure_outdoors"}
        for reason in score.evidence
    ).lower()
    assert "cities" in evidence or "movement" in evidence
    assert "event" in evidence or "trail" in evidence or "hiking" in evidence


def test_maui_resort_trip_detects_beach_and_luxury_without_primary_road_trip():
    trip = _trip(
        [
            [
                _event("maui-0", "Wailea beach sunset", "Wailea", "United States", 20.69, -156.44),
                _event("maui-1", "Resort pool and spa afternoon", "Wailea", "United States", 20.69, -156.44),
            ],
            [
                _event("maui-2", "Hotel suite breakfast and ocean relaxation", "Wailea", "United States", 20.70, -156.44),
                _event("maui-3", "Fine dining tasting menu at resort", "Wailea", "United States", 20.69, -156.44, hour=19),
            ],
        ]
    )

    blend = discover_vacation_blend(trip)

    assert "beach_relaxation" in _primary_ids(blend)
    assert "resort_luxury" in _detected_ids(blend)
    assert "road_trip" not in _primary_ids(blend)


def test_same_location_resort_trip_with_scenic_road_words_is_not_road_trip_primary():
    trip = _trip(
        [
            [
                _event(
                    "resort-road-0",
                    "Scenic road overlook viewpoint by resort beach",
                    "Wailea",
                    "United States",
                    20.69,
                    -156.44,
                ),
                _event(
                    "resort-road-1",
                    "Beach pool spa near scenic route lookout",
                    "Wailea",
                    "United States",
                    20.69,
                    -156.44,
                ),
            ],
            [
                _event(
                    "resort-road-2",
                    "Hotel suite and road viewpoint ocean sunset",
                    "Wailea",
                    "United States",
                    20.69,
                    -156.44,
                    event_type="hotel",
                ),
            ],
        ]
    )

    blend = discover_vacation_blend(trip)

    assert "road_trip" not in _primary_ids(blend)
    assert "beach_relaxation" in _primary_ids(blend)
    assert "resort_luxury" in _detected_ids(blend)


def test_las_vegas_city_trip_detects_food_culture_and_nightlife():
    trip = _trip(
        [
            [
                _event("vegas-0", "Neon Museum history tour", "Las Vegas", "United States", 36.17, -115.14, event_type="landmark"),
                _event("vegas-1", "Downtown restaurant dinner", "Las Vegas", "United States", 36.17, -115.14, hour=19, event_type="restaurant"),
            ],
            [
                _event("vegas-2", "Casino lounge and late night show", "Las Vegas", "United States", 36.11, -115.17, hour=22),
                _event("vegas-3", "Gallery art walk and cafe lunch", "Las Vegas", "United States", 36.12, -115.18, hour=12),
            ],
        ]
    )

    blend = discover_vacation_blend(trip)

    assert {"food_drink", "culture_sightseeing", "nightlife_events"} <= _detected_ids(blend)


def test_weak_single_unknown_event_has_low_confidence_warning_and_no_primary():
    trip = _trip(
        [
            [
                _event(
                    "weak-0",
                    "Unknown stop",
                    "",
                    "",
                    0.0,
                    0.0,
                    event_type="unknown",
                    photo_count=0,
                )
            ]
        ]
    )

    blend = discover_vacation_blend(trip)

    assert blend.primary == []
    assert blend.confidence == "low"
    assert any("metadata signal is weak" in warning for warning in blend.warnings)


def test_diagnostics_include_counts_and_raw_theme_scores():
    trip = _trip(
        [
            [
                _event("diag-0", "Museum cafe", "Paris", "France", 48.86, 2.35, event_type="restaurant"),
                _event("diag-1", "Historic garden walk", "Paris", "France", 48.86, 2.34),
            ]
        ]
    )

    blend = discover_vacation_blend(trip)

    assert blend.diagnostics["event_count"] == 2
    assert blend.diagnostics["photo_count"] == 6
    assert blend.diagnostics["city_count"] == 1
    assert blend.diagnostics["country_count"] == 1
    assert set(blend.diagnostics["theme_scores"]) >= {
        "road_trip",
        "adventure_outdoors",
        "culture_sightseeing",
        "food_drink",
        "beach_relaxation",
        "nightlife_events",
        "family_friends",
        "resort_luxury",
        "shopping_city",
        "wellness_slow",
        "nature_wildlife",
    }
