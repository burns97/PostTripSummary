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
    address: str | None = None,
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
            address=address if address is not None else f"{name}, {city}",
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


def test_long_haul_flight_jumps_are_excluded_from_destination_movement():
    trip = _trip(
        [
            [
                _event("haul-0", "Columbus airport departure", "Columbus", "United States", 39.99, -82.89, event_type="transit"),
                _event("haul-1", "Dallas airport layover", "Dallas", "United States", 32.90, -97.04, event_type="transit"),
            ],
            [
                _event("haul-2", "Auckland airport arrival", "Auckland", "New Zealand", -36.85, 174.76, event_type="transit"),
            ],
            [
                _event("haul-3", "Scenic drive to Rotorua lookout", "Rotorua", "New Zealand", -38.14, 176.25),
            ],
            [
                _event("haul-4", "Lake Taupo viewpoint", "Taupo", "New Zealand", -38.69, 176.07),
            ],
            [
                _event("haul-5", "Glacier hiking trail", "Wanaka", "New Zealand", -44.70, 169.13),
            ],
        ]
    )

    blend = discover_vacation_blend(trip)

    assert blend.diagnostics["gps_distance_km"] > 10000
    assert blend.diagnostics["long_haul_segment_count"] >= 1
    assert blend.diagnostics["long_haul_transit_km"] > 9000
    assert blend.diagnostics["destination_movement_km"] < blend.diagnostics["gps_distance_km"]
    assert "road_trip" in _primary_ids(blend)
    road_trip = next(score for score in blend.primary if score.theme_id == "road_trip")
    assert any("destination movement" in item.lower() for item in road_trip.evidence)


def test_ordinary_lodging_and_restaurants_do_not_become_primary_themes():
    trip = _trip(
        [
            [
                _event("logistics-0", "Check in: Airport Hotel", "Auckland", "New Zealand", -36.85, 174.76, event_type="hotel"),
                _event("logistics-1", "Casual restaurant lunch", "Auckland", "New Zealand", -36.85, 174.76, event_type="restaurant"),
                _event("logistics-2", "Neighborhood restaurant dinner", "Auckland", "New Zealand", -36.85, 174.76, event_type="restaurant"),
            ],
            [
                _event("logistics-3", "Check out: Airport Hotel", "Auckland", "New Zealand", -36.85, 174.76, event_type="hotel"),
                _event("logistics-4", "Cafe breakfast", "Auckland", "New Zealand", -36.85, 174.76, event_type="restaurant"),
                _event("logistics-5", "Waterfront museum visit", "Auckland", "New Zealand", -36.85, 174.76, event_type="landmark"),
            ],
        ]
    )

    blend = discover_vacation_blend(trip)

    assert "resort_luxury" not in _primary_ids(blend)
    assert "food_drink" not in _primary_ids(blend)


def test_address_road_and_street_words_do_not_create_theme_matches():
    trip = _trip(
        [
            [
                _event(
                    "address-0",
                    "Check in: Rotorua Airbnb",
                    "Rotorua",
                    "New Zealand",
                    -38.14,
                    176.25,
                    event_type="hotel",
                    address="12 Lake Road",
                ),
                _event(
                    "address-1",
                    "Check out: Rotorua Airbnb",
                    "Rotorua",
                    "New Zealand",
                    -38.14,
                    176.25,
                    event_type="hotel",
                    address="12 Lake Road",
                ),
                _event(
                    "address-2",
                    "Check in: Wanaka Airbnb",
                    "Wanaka",
                    "New Zealand",
                    -44.70,
                    169.13,
                    event_type="hotel",
                    address="44 Main Street",
                ),
                _event(
                    "address-3",
                    "Check out: Wanaka Airbnb",
                    "Wanaka",
                    "New Zealand",
                    -44.70,
                    169.13,
                    event_type="hotel",
                    address="44 Main Street",
                ),
            ],
        ]
    )

    blend = discover_vacation_blend(trip)

    assert "road_trip" not in _primary_ids(blend)
    assert "shopping_city" not in _detected_ids(blend)


def test_natural_landmarks_do_not_make_culture_primary_by_event_type_alone():
    trip = _trip(
        [
            [
                _event("nature-landmark-0", "Waimangu volcanic valley lake", "Rotorua", "New Zealand", -38.28, 176.38, event_type="landmark"),
                _event("nature-landmark-1", "Glacier lake viewpoint", "Wanaka", "New Zealand", -44.70, 169.13, event_type="landmark"),
            ],
            [
                _event("nature-landmark-2", "Fjord waterfall lookout", "Te Anau", "New Zealand", -45.41, 167.72, event_type="landmark"),
                _event("nature-landmark-3", "Mountain forest walk", "Queenstown", "New Zealand", -45.03, 168.66, event_type="landmark"),
            ],
        ]
    )

    blend = discover_vacation_blend(trip)

    assert "nature_wildlife" in _detected_ids(blend)
    assert "culture_sightseeing" not in _primary_ids(blend)


def test_partial_trip_sample_adds_coverage_diagnostics_and_warning():
    start = date(2026, 1, 1)
    trip = Trip(
        name="Partial Trip",
        date_range=(start, start + timedelta(days=16)),
        days=[
            Day(date=start, events=[_event("partial-0", "Museum restaurant", "Auckland", "New Zealand", -36.85, 174.76, event_type="restaurant")]),
            Day(date=start + timedelta(days=1), events=[_event("partial-1", "Hotel breakfast", "Auckland", "New Zealand", -36.85, 174.76, event_type="hotel")]),
            Day(date=start + timedelta(days=2), events=[_event("partial-2", "City gallery walk", "Auckland", "New Zealand", -36.85, 174.76, event_type="landmark")]),
        ],
    )

    blend = discover_vacation_blend(trip)

    coverage = blend.diagnostics["coverage"]
    assert coverage["expected_days"] == 17
    assert coverage["observed_days"] == 3
    assert coverage["coverage_confidence"] == "low"
    assert any("partial trip sample" in warning for warning in blend.warnings)
