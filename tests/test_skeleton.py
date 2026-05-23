# tests/test_skeleton.py
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from post_trip_summary.models import (
    Photo, Location, Accommodation, Transit, TransitPoint, Expense, Event, Day, Trip,
)
from post_trip_summary.pipeline.skeleton import (
    build_skeleton, _match_cluster_to_itinerary, _match_cluster_to_expense,
    _classify_event, _assign_event_ids,
)


def _photo(ts: str, lat: float, lon: float) -> Photo:
    return Photo(path=Path(f"/p/{ts}.jpg"), timestamp=datetime.fromisoformat(ts), gps=(lat, lon))


def _make_cluster(ts_start: str, ts_end: str, lat: float, lon: float, count: int = 5) -> dict:
    return {
        "photos": [_photo(ts_start, lat, lon)] * count,
        "centroid": (lat, lon),
        "time_range": (datetime.fromisoformat(ts_start), datetime.fromisoformat(ts_end)),
    }


def test_match_cluster_to_accommodation():
    cluster = _make_cluster("2026-03-05 15:30:00", "2026-03-05 16:00:00", 48.857, 2.362)
    acc = Accommodation(
        name="Hotel Le Marais",
        location=Location(lat=48.857, lon=2.362, name="Hotel Le Marais", address="123 Rue", city="Paris", country="France"),
        check_in=datetime(2026, 3, 5, 15, 0),
        check_out=datetime(2026, 3, 8, 11, 0),
        sources=["itinerary"],
    )
    match = _match_cluster_to_itinerary(cluster, [acc], [])
    assert match is not None
    assert match["name"] == "Hotel Le Marais"
    assert match["type"] == "hotel"


def test_match_cluster_to_expense():
    cluster = _make_cluster("2026-03-05 19:00:00", "2026-03-05 19:30:00", 48.858, 2.294)
    expenses = [
        Expense(date=date(2026, 3, 5), amount=87.5, currency="EUR", merchant="REST LE PETIT", category="dining", source="credit_card"),
    ]
    match = _match_cluster_to_expense(cluster, expenses)
    assert match is not None
    assert match.merchant == "REST LE PETIT"


def test_expense_not_reused_after_match():
    """Once an expense is matched (event_id set), it should not match another cluster."""
    expenses = [
        Expense(date=date(2026, 3, 5), amount=12.0, currency="NZD", merchant="YAZA GELATO", category="dining", source="credit_card"),
    ]
    cluster1 = _make_cluster("2026-03-05 08:00:00", "2026-03-05 08:15:00", -36.85, 174.76)
    match1 = _match_cluster_to_expense(cluster1, expenses)
    assert match1 is not None
    # Simulate skeleton marking it consumed
    match1.event_id = "pending"
    cluster2 = _make_cluster("2026-03-05 12:00:00", "2026-03-05 13:00:00", -36.90, 174.80)
    match2 = _match_cluster_to_expense(cluster2, expenses)
    assert match2 is None


def test_classify_event_restaurant():
    assert _classify_event(expense_category="dining") == "restaurant"


def test_classify_event_unknown():
    assert _classify_event() == "unknown"


def test_assign_event_ids():
    events = [
        Event(id="", type="landmark", name="A", time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 11, 0)),
              location=Location(lat=0, lon=0, name="", address=None, city="", country="")),
        Event(id="", type="restaurant", name="B", time_range=(datetime(2026, 3, 5, 12, 0), datetime(2026, 3, 5, 13, 0)),
              location=Location(lat=0, lon=0, name="", address=None, city="", country="")),
    ]
    days = [Day(date=date(2026, 3, 5), events=events)]
    _assign_event_ids(days)
    assert days[0].events[0].id == "day01-event01"
    assert days[0].events[1].id == "day01-event02"


def test_activity_type_used_in_match():
    """When an activity has an explicit type, the match returns it instead of 'activity'."""
    cluster = _make_cluster("2026-02-23 10:00:00", "2026-02-23 11:00:00", -37.8, 175.7)
    activities = [
        {"name": "Hobbiton", "city": "Matamata", "country": "New Zealand",
         "date": "2026-02-23", "type": "landmark", "time": "09:30", "notes": ""},
    ]
    match = _match_cluster_to_itinerary(cluster, [], activities)
    assert match is not None
    assert match["name"] == "Hobbiton"
    assert match["type"] == "landmark"


def test_activity_default_type():
    """Activities without a type field default to 'activity'."""
    cluster = _make_cluster("2026-03-06 19:00:00", "2026-03-06 20:00:00", 48.86, 2.29)
    activities = [
        {"name": "Seine River Cruise", "city": "Paris", "country": "France",
         "date": "2026-03-06", "time": "19:00", "notes": ""},
    ]
    match = _match_cluster_to_itinerary(cluster, [], activities)
    assert match is not None
    assert match["type"] == "activity"


def test_city_aware_activity_matching():
    """When multiple activities share a date, prefer the one matching the cluster's city."""
    cluster = _make_cluster("2026-02-25 12:00:00", "2026-02-25 13:00:00", -44.0, 169.3)
    cluster["reverse_geo"] = {"city": "Haast Pass"}
    activities = [
        {"name": "Fantail Falls", "city": "Haast Pass", "country": "New Zealand",
         "date": "2026-02-25", "type": "landmark", "time": "", "notes": "Drive stop"},
        {"name": "The Neck", "city": "Wanaka", "country": "New Zealand",
         "date": "2026-02-25", "type": "landmark", "time": "", "notes": ""},
    ]
    match = _match_cluster_to_itinerary(cluster, [], activities)
    assert match is not None
    assert match["name"] == "Fantail Falls"


def test_city_aware_fallback_none():
    """When no activity's city matches the cluster's city, return None."""
    cluster = _make_cluster("2026-02-25 15:00:00", "2026-02-25 16:00:00", -44.5, 169.0)
    cluster["reverse_geo"] = {"city": "SomeOtherPlace"}
    activities = [
        {"name": "Blue Pools", "city": "Haast Pass", "country": "New Zealand",
         "date": "2026-02-25", "type": "landmark", "time": "", "notes": ""},
        {"name": "The Neck", "city": "Wanaka", "country": "New Zealand",
         "date": "2026-02-25", "type": "landmark", "time": "", "notes": ""},
    ]
    match = _match_cluster_to_itinerary(cluster, [], activities)
    assert match is None


def test_no_match_when_city_differs():
    """Cluster in Rotorua should not match an activity in Hamilton."""
    cluster = _make_cluster("2026-02-24 10:00:00", "2026-02-24 11:00:00", -38.14, 176.25)
    cluster["reverse_geo"] = {"city": "Rotorua"}
    activities = [
        {"name": "Hamilton Gardens", "city": "Hamilton", "country": "New Zealand",
         "date": "2026-02-24", "type": "landmark", "time": "14:00", "notes": ""},
    ]
    match = _match_cluster_to_itinerary(cluster, [], activities)
    assert match is None


def test_match_when_activity_has_no_city():
    """Activity with blank city still matches by date as a weak candidate."""
    cluster = _make_cluster("2026-02-24 10:00:00", "2026-02-24 11:00:00", -38.14, 176.25)
    cluster["reverse_geo"] = {"city": "Rotorua"}
    activities = [
        {"name": "Mystery Event", "city": "", "country": "New Zealand",
         "date": "2026-02-24", "type": "activity", "time": "", "notes": ""},
    ]
    match = _match_cluster_to_itinerary(cluster, [], activities)
    assert match is not None
    assert match["name"] == "Mystery Event"


def test_accommodation_events_in_skeleton():
    """Verify check-in/check-out events appear in the skeleton timeline."""
    photos = [_photo("2026-03-05 14:00:00", 48.858, 2.294)]
    acc = Accommodation(
        name="Hotel Le Marais",
        location=Location(lat=48.857, lon=2.362, name="Hotel Le Marais", address="123 Rue", city="Paris", country="France"),
        check_in=datetime(2026, 3, 5, 15, 0),
        check_out=datetime(2026, 3, 7, 11, 0),
        sources=["itinerary"],
    )
    trip_data = {
        "photos": photos,
        "accommodations": [acc],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    trip = build_skeleton(trip_data)
    # Find check-in and check-out events across all days
    event_names = [e.name for d in trip.days for e in d.events]
    assert "Check in: Hotel Le Marais" in event_names
    assert "Check out: Hotel Le Marais" in event_names


def test_geo_poi_beats_itinerary_name():
    """When reverse geocode has a specific POI name, it wins over itinerary name."""
    cluster = _make_cluster("2026-02-24 10:00:00", "2026-02-24 11:00:00", -37.81, 175.28)
    cluster["reverse_geo"] = {
        "city": "Hamilton", "poi_name": "Hamilton Gardens", "area_name": "Hamilton",
        "place_name": "Hamilton Gardens", "country": "NZ",
    }
    activities = [
        {"name": "Visit Hamilton Gardens", "city": "Hamilton", "country": "New Zealand",
         "date": "2026-02-24", "type": "landmark", "time": "10:00", "notes": ""},
    ]
    itinerary_match = _match_cluster_to_itinerary(cluster, [], activities)
    assert itinerary_match is not None

    # Simulate name resolution logic from build_skeleton
    geo = cluster["reverse_geo"]
    geo_poi = geo.get("poi_name", "")
    google_match = None
    dayone_name = ""

    if google_match:
        name = google_match.get("name", "")
    elif geo_poi:
        name = geo_poi
    elif itinerary_match:
        name = itinerary_match.get("name", "")
    elif dayone_name:
        name = dayone_name
    else:
        name = geo.get("area_name", "")

    assert name == "Hamilton Gardens"


def test_itinerary_name_when_no_poi():
    """When geocode has no specific POI, itinerary name is used."""
    cluster = _make_cluster("2026-02-24 10:00:00", "2026-02-24 11:00:00", -37.81, 175.28)
    cluster["reverse_geo"] = {
        "city": "Hamilton", "poi_name": "", "area_name": "Hamilton",
        "place_name": "Hamilton", "country": "NZ",
    }
    activities = [
        {"name": "Hamilton Gardens", "city": "Hamilton", "country": "New Zealand",
         "date": "2026-02-24", "type": "landmark", "time": "10:00", "notes": ""},
    ]
    itinerary_match = _match_cluster_to_itinerary(cluster, [], activities)
    assert itinerary_match is not None

    geo = cluster["reverse_geo"]
    geo_poi = geo.get("poi_name", "")

    if geo_poi:
        name = geo_poi
    elif itinerary_match:
        name = itinerary_match.get("name", "")
    else:
        name = geo.get("area_name", "")

    assert name == "Hamilton Gardens"


def test_expense_never_sets_name():
    """Expense matches cluster but event name comes from geocode, not merchant."""
    cluster = _make_cluster("2026-03-05 08:00:00", "2026-03-05 08:15:00", -36.85, 174.76)
    cluster["reverse_geo"] = {
        "city": "Auckland", "poi_name": "", "area_name": "Auckland",
        "place_name": "Auckland", "country": "NZ",
    }
    expenses = [
        Expense(date=date(2026, 3, 5), amount=12.0, currency="NZD",
                merchant="YAZA GELATO", category="dining", source="credit_card"),
    ]
    expense_match = _match_cluster_to_expense(cluster, expenses)
    assert expense_match is not None

    # Simulate photos-first name resolution — expense never sets name
    geo = cluster["reverse_geo"]
    geo_poi = geo.get("poi_name", "")
    geo_area = geo.get("area_name", "") or geo.get("city", "")
    google_match = None
    itinerary_match = None
    dayone_name = ""

    if google_match:
        name = google_match.get("name", "")
    elif geo_poi:
        name = geo_poi
    elif itinerary_match:
        name = itinerary_match.get("name", "")
    elif dayone_name:
        name = dayone_name
    else:
        name = geo_area

    # Name should be "Auckland" from geo, NOT "YAZA GELATO" from expense
    assert name == "Auckland"
    assert name != "YAZA GELATO"


def test_build_skeleton_basic():
    photos = [
        _photo("2026-03-05 10:00:00", 48.858, 2.294),
        _photo("2026-03-05 10:05:00", 48.858, 2.295),
    ]
    trip_data = {
        "photos": photos,
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    trip = build_skeleton(trip_data, gap_minutes=15, distance_meters=200)
    assert isinstance(trip, Trip)
    assert len(trip.days) >= 1
    assert len(trip.days[0].events) >= 1


def test_build_skeleton_persists_geo_context_for_discovery():
    photos = [
        _photo("2026-03-05 10:00:00", -38.288, 176.390),
        _photo("2026-03-05 10:05:00", -38.289, 176.391),
    ]
    trip_data = {
        "photos": photos,
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    mock_geo = {
        "city": "Rotorua",
        "country": "NZ",
        "admin1": "Bay of Plenty",
        "admin2": "",
        "suburb": "",
        "municipality": "",
        "tourism": "Waimangu Volcanic Valley",
        "amenity": "",
        "leisure": "",
        "historic": "",
        "shop": "",
        "natural": "",
        "road": "",
        "poi_name": "Waimangu Volcanic Valley",
        "area_name": "Rotorua",
        "place_name": "Waimangu Volcanic Valley",
        "overpass_poi_name": "Waimangu Volcanic Valley",
        "overpass_pois": [
            {
                "name": "Waimangu Volcanic Valley",
                "category": "tourism",
                "type": "attraction",
                "distance_m": 24.4,
            },
            {
                "name": "Waimangu Cafe",
                "category": "amenity",
                "type": "cafe",
                "distance_m": 80.0,
            },
        ],
    }

    with (
        patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo),
        patch("post_trip_summary.pipeline.skeleton.resolve_airport_candidate", return_value=None),
    ):
        trip = build_skeleton(trip_data, gap_minutes=15, distance_meters=200)

    event = trip.days[0].events[0]
    assert event.geo_context["location_granularity"] == "poi"
    assert event.geo_context["poi_category"] == "tourism"
    assert event.geo_context["nearby_pois"][0]["type"] == "attraction"
    assert event.geo_context["gps_photo_count"] == 2
    assert event.geo_context["is_airport"] is False


def test_build_skeleton_prefers_airport_over_terminal_amenity():
    photos = [
        _photo("2026-02-18 15:25:21", 39.99786388888889, -82.88245277777777),
    ]
    trip_data = {
        "photos": photos,
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    mock_geo = {
        "city": "Columbus",
        "country": "US",
        "admin1": "Ohio",
        "admin2": "Franklin County",
        "suburb": "",
        "municipality": "",
        "tourism": "",
        "amenity": "Brewdog",
        "leisure": "",
        "historic": "",
        "shop": "",
        "natural": "",
        "road": "",
        "poi_name": "Brewdog",
        "area_name": "Columbus",
        "place_name": "Columbus",
        "overpass_poi_name": "John Glenn Columbus International Airport",
        "overpass_pois": [
            {
                "name": "John Glenn Columbus International Airport",
                "category": "aeroway",
                "type": "aerodrome",
                "distance_m": 140.0,
            },
            {
                "name": "Brewdog",
                "category": "amenity",
                "type": "bar",
                "distance_m": 14.0,
            },
            {
                "name": "Eddie George's Grille 27",
                "category": "amenity",
                "type": "pub",
                "distance_m": 42.0,
            },
        ],
    }

    with (
        patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo),
        patch("post_trip_summary.pipeline.skeleton.resolve_airport_candidate", return_value=None),
    ):
        trip = build_skeleton(trip_data, gap_minutes=15, distance_meters=200)

    event = trip.days[0].events[0]
    assert event.name == "John Glenn Columbus International Airport"
    assert event.geo_context["is_airport"] is True
    assert event.geo_context["airport_name"] == "John Glenn Columbus International Airport"
    assert event.name_candidates["Airport"] == "John Glenn Columbus International Airport"
    assert "Brewdog" in event.name_candidates.values()


def test_build_skeleton_does_not_promote_terminal_level_without_airport_name():
    photos = [
        _photo("2026-02-18 15:25:21", 39.99786388888889, -82.88245277777777),
    ]
    trip_data = {
        "photos": photos,
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    mock_geo = {
        "city": "Columbus",
        "country": "US",
        "admin1": "Ohio",
        "admin2": "Franklin County",
        "suburb": "",
        "municipality": "",
        "tourism": "",
        "aeroway": "Ticketing Level",
        "amenity": "",
        "leisure": "",
        "historic": "",
        "shop": "",
        "natural": "",
        "road": "",
        "poi_name": "",
        "area_name": "Columbus",
        "place_name": "Columbus",
        "overpass_poi_name": "Ticketing Level",
        "overpass_pois": [
            {
                "name": "Ticketing Level",
                "category": "aeroway",
                "type": "terminal",
                "distance_m": 73.0,
            },
            {
                "name": "Brewdog",
                "category": "amenity",
                "type": "bar",
                "distance_m": 14.0,
            },
        ],
    }

    with (
        patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo),
        patch("post_trip_summary.pipeline.skeleton.resolve_airport_candidate", return_value=None),
    ):
        trip = build_skeleton(trip_data, gap_minutes=15, distance_meters=200)

    event = trip.days[0].events[0]
    assert event.name == "Columbus"
    assert event.geo_context["is_airport"] is True
    assert event.geo_context["airport_name"] == ""
    assert "Ticketing Level" in event.name_candidates.values()


def test_build_skeleton_uses_local_airport_resolver_for_terminal_only_geocode():
    photos = [
        _photo("2026-02-18 15:25:21", 39.99786388888889, -82.88245277777777),
    ]
    trip_data = {
        "photos": photos,
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    mock_geo = {
        "city": "Columbus",
        "country": "US",
        "admin1": "Ohio",
        "admin2": "Franklin County",
        "suburb": "",
        "municipality": "",
        "tourism": "",
        "aeroway": "Ticketing Level",
        "amenity": "",
        "leisure": "",
        "historic": "",
        "shop": "",
        "natural": "",
        "road": "",
        "poi_name": "Ticketing Level",
        "area_name": "Columbus",
        "place_name": "Ticketing Level",
        "overpass_poi_name": "Ticketing Level",
        "overpass_pois": [
            {
                "name": "Ticketing Level",
                "category": "aeroway",
                "type": "terminal",
                "distance_m": 73.0,
            },
            {
                "name": "Brewdog",
                "category": "amenity",
                "type": "bar",
                "distance_m": 14.0,
            },
        ],
    }
    airport_candidate = {
        "name": "John Glenn Columbus International Airport",
        "display_name": "John Glenn Columbus International Airport (CMH)",
        "iata_code": "CMH",
        "icao_code": "KCMH",
        "type": "large_airport",
        "distance_m": 740.0,
        "source": "airport_seed",
    }

    with (
        patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo),
        patch("post_trip_summary.pipeline.skeleton.resolve_airport_candidate", return_value=airport_candidate),
    ):
        trip = build_skeleton(trip_data, gap_minutes=15, distance_meters=200)

    event = trip.days[0].events[0]
    assert event.name == "John Glenn Columbus International Airport (CMH)"
    assert event.name_candidates["Airport"] == "John Glenn Columbus International Airport (CMH)"
    assert event.geo_context["airport_name"] == "John Glenn Columbus International Airport (CMH)"
    assert event.geo_context["airport_iata"] == "CMH"


def test_build_skeleton_prefers_area_for_broad_walking_cluster_with_minor_poi():
    photos = [
        _photo("2026-02-20 10:28:27", -36.849716666666666, 174.75965833333333),
        _photo("2026-02-20 10:44:10", -36.84400277777778, 174.7633361111111),
        _photo("2026-02-20 11:24:19", -36.84160555555556, 174.75904722222222),
        _photo("2026-02-20 11:58:48", -36.84284166666667, 174.76634166666668),
    ]
    trip_data = {
        "photos": photos,
        "accommodations": [],
        "transits": [],
        "activities": [],
        "expenses": [],
        "google_maps": {"place_visits": [], "activity_segments": []},
        "apple_health": [],
        "dayone": [],
    }
    mock_geo = {
        "city": "Auckland Central",
        "country": "NZ",
        "admin1": "Auckland Region",
        "admin2": "Auckland",
        "suburb": "",
        "municipality": "",
        "tourism": "Through Work We Will Live",
        "amenity": "",
        "leisure": "",
        "historic": "",
        "shop": "",
        "natural": "",
        "road": "",
        "poi_name": "Through Work We Will Live",
        "area_name": "Auckland Central",
        "place_name": "Auckland Central",
        "overpass_poi_name": "Through Work We Will Live",
        "overpass_pois": [
            {
                "name": "Through Work We Will Live",
                "category": "tourism",
                "type": "artwork",
                "distance_m": 121.0,
            },
            {
                "name": "Long Modified Bench",
                "category": "tourism",
                "type": "artwork",
                "distance_m": 124.0,
            },
            {
                "name": "Horse trough",
                "category": "historic",
                "type": "memorial",
                "distance_m": 104.0,
            },
        ],
    }

    with patch("post_trip_summary.pipeline.skeleton.reverse_geocode", return_value=mock_geo):
        trip = build_skeleton(trip_data, gap_minutes=15, distance_meters=200)

    event = trip.days[0].events[0]
    assert event.name == "Auckland Central"
    assert event.geo_context["is_broad_walking_cluster"] is True
    assert event.name_candidates["Area"] == "Auckland Central"
    assert "Through Work We Will Live" in event.name_candidates.values()
