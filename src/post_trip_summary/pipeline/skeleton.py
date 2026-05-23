"""Build trip skeleton from clustered photos and supplementary data."""
from datetime import date, datetime, timedelta
from collections import defaultdict

from geopy.distance import geodesic

from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Accommodation, Transit, Expense,
)
from post_trip_summary.geo.airports import resolve_airport_candidate
from post_trip_summary.geo.clustering import build_clusters, merge_nearby_clusters, detect_and_collapse_transit
from post_trip_summary.geo.context import build_geo_context
from post_trip_summary.geo.interpolate import interpolate_missing_gps
from post_trip_summary.geo.reverse_geocode import reverse_geocode

MINOR_WALKING_POI_TYPES = {
    ("amenity", "bar"),
    ("amenity", "cafe"),
    ("amenity", "pub"),
    ("amenity", "restaurant"),
    ("historic", "memorial"),
    ("tourism", "artwork"),
    ("tourism", "hotel"),
    ("tourism", "information"),
}


def _match_cluster_to_itinerary(
    cluster: dict,
    accommodations: list[Accommodation],
    activities: list[dict],
) -> dict | None:
    """Check if cluster matches a known itinerary item by location and date."""
    centroid = cluster["centroid"]
    if not centroid:
        return None
    cluster_date = cluster["time_range"][0].date()

    # Check accommodations
    for acc in accommodations:
        if acc.location.lat == 0.0 and acc.location.lon == 0.0:
            continue
        if acc.check_in.date() <= cluster_date <= acc.check_out.date():
            dist = geodesic(centroid, (acc.location.lat, acc.location.lon)).meters
            if dist < 500:
                return {"name": acc.name, "type": "hotel", "source": "itinerary", "location": acc.location}

    # Check activities — require city match, not just date
    cluster_city = cluster.get("reverse_geo", {}).get("city", "")
    candidates = []
    for act in activities:
        act_date = date.fromisoformat(act["date"]) if isinstance(act["date"], str) else act["date"]
        if act_date != cluster_date:
            continue
        act_city = act.get("city", "")
        act_type = act.get("type", "activity")
        candidate = {"name": act["name"], "type": act_type, "source": "itinerary", "city": act_city}
        # If cluster has a city and activity has a city, only include if they match
        if cluster_city and act_city:
            if cluster_city.lower() == act_city.lower():
                candidates.append(candidate)
        elif not act_city:
            # Activity has no city — include as weak candidate
            candidates.append(candidate)
        elif not cluster_city:
            # Cluster has no city — include all date-matched activities
            candidates.append(candidate)

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    # Multiple candidates — prefer city match, then first
    for c in candidates:
        if c["city"] and cluster_city and cluster_city.lower() == c["city"].lower():
            return c
    return candidates[0]


def _match_cluster_to_expense(cluster: dict, expenses: list[Expense]) -> Expense | None:
    """Find an expense on the same date as the cluster."""
    cluster_date = cluster["time_range"][0].date()
    for exp in expenses:
        if exp.date == cluster_date and exp.event_id is None:
            return exp
    return None


def _match_cluster_to_google_maps(cluster: dict, place_visits: list[dict]) -> dict | None:
    """Match cluster to a Google Maps place visit by time and location proximity."""
    centroid = cluster["centroid"]
    c_start, c_end = cluster["time_range"]
    for visit in place_visits:
        v_start = visit.get("start")
        v_end = visit.get("end")
        if not v_start or not v_end:
            continue
        # Check time overlap
        if c_start <= v_end and c_end >= v_start:
            if centroid and visit.get("lat") and visit.get("lon"):
                dist = geodesic(centroid, (visit["lat"], visit["lon"])).meters
                if dist < 500:
                    return visit
    return None


def _classify_event(
    itinerary_match: dict | None = None,
    expense_category: str | None = None,
    google_match: dict | None = None,
) -> str:
    """Determine event type from available signals."""
    if itinerary_match:
        return itinerary_match.get("type", "unknown")
    if expense_category:
        category_map = {"dining": "restaurant", "transport": "transit", "activity": "activity", "shopping": "landmark"}
        return category_map.get(expense_category.lower(), "unknown")
    return "unknown"


def _assign_event_ids(days: list[Day]) -> None:
    """Assign unique IDs to all events."""
    for day_idx, day in enumerate(days):
        for event_idx, event in enumerate(day.events):
            event.id = f"day{day_idx + 1:02d}-event{event_idx + 1:02d}"


def build_skeleton(
    trip_data: dict,
    gap_minutes: int = 15,
    distance_meters: int = 200,
    progress_callback=None,
) -> Trip:
    """Build a Trip skeleton from ingested data."""
    photos: list[Photo] = trip_data.get("photos", [])
    accommodations: list[Accommodation] = trip_data.get("accommodations", [])
    transits: list[Transit] = trip_data.get("transits", [])
    activities: list[dict] = trip_data.get("activities", [])
    expenses: list[Expense] = trip_data.get("expenses", [])
    google_maps = trip_data.get("google_maps", {})
    place_visits = google_maps.get("place_visits", [])
    health_workouts = trip_data.get("apple_health", [])
    dayone_entries = trip_data.get("dayone", [])

    # Interpolate GPS for photos missing coordinates before clustering
    interpolate_missing_gps(photos)

    # Cluster photos, then merge nearby and detect transit
    clusters = build_clusters(photos, gap_minutes, distance_meters)
    clusters = merge_nearby_clusters(clusters)
    clusters = detect_and_collapse_transit(clusters)

    # Determine date range
    all_dates = set()
    for c in clusters:
        all_dates.add(c["time_range"][0].date())
        all_dates.add(c["time_range"][1].date())
    for acc in accommodations:
        d = acc.check_in.date()
        while d <= acc.check_out.date():
            all_dates.add(d)
            d += timedelta(days=1)

    if not all_dates:
        return Trip(name="", date_range=(date.today(), date.today()))

    date_range = (min(all_dates), max(all_dates))

    # Build events from clusters
    events_by_date: dict[date, list[Event]] = defaultdict(list)

    for idx, cluster in enumerate(clusters):
        if progress_callback:
            progress_callback("geocoding", idx + 1, len(clusters),
                            f"Reverse geocoding cluster {idx + 1}/{len(clusters)}...")
        c_date = cluster["time_range"][0].date()
        centroid = cluster["centroid"]

        # Pre-compute reverse geocode so city-aware matching can use it
        if centroid:
            geo = reverse_geocode(centroid[0], centroid[1])
            cluster["reverse_geo"] = geo
            if progress_callback:
                name = geo.get("name", geo.get("city", ""))
                progress_callback("geocoding", idx + 1, len(clusters),
                                f"Found: {name}" if name else f"Geocoded cluster {idx + 1}")
        else:
            geo = {}
            cluster["reverse_geo"] = geo

        # Cross-reference
        itinerary_match = _match_cluster_to_itinerary(cluster, accommodations, activities)
        expense_match = _match_cluster_to_expense(cluster, expenses)
        google_match = _match_cluster_to_google_maps(cluster, place_visits)

        # Mark expense as consumed so it doesn't match other clusters
        if expense_match:
            expense_match.event_id = "pending"

        # Determine name and type
        sources = ["exif"]

        # Check Apple Health workouts for time overlap
        for workout in health_workouts:
            w_start = workout.get("start")
            w_end = workout.get("end")
            if w_start and w_end and cluster["time_range"][0] <= w_end and cluster["time_range"][1] >= w_start:
                sources.append("apple_health")
                break

        # Check Day One entries for time overlap
        dayone_name = ""
        for entry in dayone_entries:
            e_ts = entry.get("timestamp")
            if e_ts and cluster["time_range"][0] <= e_ts <= cluster["time_range"][1]:
                sources.append("dayone")
                dayone_name = entry.get("place_name", "")
                break
        event_type = "unknown"
        name = ""

        # Transit clusters detected by driving-day heuristic
        if cluster.get("transit_hint"):
            event_type = "transit"

        # Photos-first name resolution:
        # 1. Google Maps is high-confidence (GPS + time verified) — it wins
        # 2. Reverse geocode found a specific POI — use it
        # 3. Itinerary matched by city+date — use only if geocode had no specific POI
        # 4. Day One entry name
        # 5. Fall back to area name from geocode
        geo_poi = geo.get("poi_name", "")
        overpass_poi = geo.get("overpass_poi_name", "")
        geo_area = geo.get("area_name", "") or geo.get("city", "")
        geo_context = build_geo_context(geo, cluster) if centroid else {}
        airport_candidate = (
            resolve_airport_candidate(centroid[0], centroid[1], geo_context)
            if centroid else None
        )
        if airport_candidate:
            airport_name = str(airport_candidate["display_name"])
            geo_context.update(
                {
                    "airport_name": airport_name,
                    "airport_iata": airport_candidate.get("iata_code", ""),
                    "airport_icao": airport_candidate.get("icao_code", ""),
                    "airport_distance_m": airport_candidate.get("distance_m", 0.0),
                    "airport_source": airport_candidate.get("source", ""),
                    "is_airport": True,
                }
            )
        else:
            airport_name = str(geo_context.get("airport_name", "") or "")

        # Collect all name candidates for the review UI
        name_candidates = {}
        if google_match and google_match.get("name"):
            name_candidates["Google Maps"] = google_match["name"]
        if airport_name:
            name_candidates["Airport"] = airport_name
        if geo_poi:
            name_candidates["Geocode POI"] = geo_poi
        # Add individual geocoder POI fields as separate candidates when they differ
        for field_label, field_key in [
            ("Tourism", "tourism"), ("Amenity", "amenity"),
            ("Leisure", "leisure"), ("Historic", "historic"),
        ]:
            val = geo.get(field_key, "")
            if val and val != geo_poi:
                name_candidates[field_label] = val
        # Add top Overpass results (not just the best one)
        overpass_pois = geo.get("overpass_pois", [])
        seen_names = set(name_candidates.values())
        for i, poi in enumerate(overpass_pois[:5]):
            if poi["name"] not in seen_names:
                label = f"Nearby: {poi['category']}" if i == 0 else f"Nearby: {poi['category']} ({i+1})"
                name_candidates[label] = poi["name"]
                seen_names.add(poi["name"])
        if itinerary_match and itinerary_match.get("name"):
            name_candidates["Itinerary"] = itinerary_match["name"]
        if dayone_name:
            name_candidates["Day One"] = dayone_name
        if geo_area:
            name_candidates["Area"] = geo_area

        # Prefer Overpass "destination" POI (attraction, museum, etc.) over
        # a geocoder POI that's a minor feature inside it (e.g.,
        # "Hobbiton Movie Set Tour" over "Vegetable Gardens" inside it)
        overpass_destination = ""
        for op in overpass_pois:
            if op.get("category") == "tourism" and op.get("type") in (
                "attraction", "museum", "gallery", "theme_park", "zoo", "aquarium",
            ):
                overpass_destination = op["name"]
                break

        if google_match:
            name = google_match.get("name", "")
            sources.append("google_maps")
        elif airport_name:
            name = airport_name
            if airport_candidate:
                sources.append("airport_lookup")
        elif _should_prefer_area_for_airport_terminal(geo_context):
            name = geo_area
        elif _should_prefer_area_for_broad_walk(geo_context):
            name = geo_area
        elif overpass_destination and overpass_destination != geo_poi:
            name = overpass_destination
        elif geo_poi:
            name = geo_poi
        elif overpass_poi:
            name = overpass_poi
        elif itinerary_match:
            name = itinerary_match.get("name", "")
        elif dayone_name:
            name = dayone_name
        else:
            name = geo_area

        # Itinerary still provides event_type regardless of name source
        if itinerary_match:
            event_type = itinerary_match.get("type", "unknown")
            sources.append("itinerary")

        # Expenses NEVER set the name — only contribute type classification
        if expense_match:
            if event_type == "unknown":
                event_type = _classify_event(expense_category=expense_match.category)
            sources.append("credit_card")

        # Build location (reuse pre-computed reverse_geo)
        if centroid:
            place_name = geo.get("place_name", "") or geo.get("city", "")
            location = Location(
                lat=centroid[0], lon=centroid[1],
                name=name or place_name,
                address=None,
                city=geo.get("city", ""),
                country=geo.get("country", ""),
            )
        else:
            place_name = ""
            geo_context = {}
            location = Location(lat=0, lon=0, name=name, address=None, city="", country="")

        # For transit clusters, build a "City A to City B" name from endpoints
        if cluster.get("transit_hint") and not name:
            first_photo = cluster["photos"][0]
            last_photo = cluster["photos"][-1]
            if first_photo.gps and last_photo.gps:
                start_geo = reverse_geocode(first_photo.gps[0], first_photo.gps[1])
                end_geo = reverse_geocode(last_photo.gps[0], last_photo.gps[1])
                start_place = start_geo.get("place_name", "") or start_geo.get("city", "")
                end_place = end_geo.get("place_name", "") or end_geo.get("city", "")
                if start_place and end_place and start_place != end_place:
                    name = f"{start_place} to {end_place}"

        event = Event(
            id="",
            type=event_type,
            name=name or place_name or "Unknown",
            time_range=cluster["time_range"],
            location=location,
            photos=cluster["photos"],
            description="",
            notes="",
            sources=sources,
            name_candidates=name_candidates,
            geo_context=geo_context,
        )
        events_by_date[c_date].append(event)

    # Add transit events
    for transit in transits:
        t_date = transit.departure.time.date()
        # Use plain dash instead of unicode arrow to avoid encoding issues
        transit_name = f"{transit.mode.title()}: {transit.departure.name} - {transit.arrival.name}"
        transit_event = Event(
            id="",
            type="transit",
            name=transit_name,
            time_range=(transit.departure.time, transit.arrival.time),
            location=transit.departure.location,
            photos=[],
            description=str(transit.details.get("info", "")),
            notes="",
            sources=transit.sources,
        )
        events_by_date[t_date].append(transit_event)

    # Add accommodation check-in/check-out events
    for acc in accommodations:
        checkin_event = Event(
            id="",
            type="hotel",
            name=f"Check in: {acc.name}",
            time_range=(acc.check_in, acc.check_in),
            location=acc.location,
            photos=[],
            description="",
            notes="",
            sources=acc.sources,
        )
        events_by_date[acc.check_in.date()].append(checkin_event)

        checkout_event = Event(
            id="",
            type="hotel",
            name=f"Check out: {acc.name}",
            time_range=(acc.check_out, acc.check_out),
            location=acc.location,
            photos=[],
            description="",
            notes="",
            sources=acc.sources,
        )
        events_by_date[acc.check_out.date()].append(checkout_event)

    # Build days
    days = []
    current = date_range[0]
    while current <= date_range[1]:
        day_events = sorted(events_by_date.get(current, []), key=lambda e: e.time_range[0])
        days.append(Day(date=current, events=day_events))
        current += timedelta(days=1)

    _assign_event_ids(days)

    return Trip(
        name="",
        date_range=date_range,
        days=days,
        accommodations=accommodations,
        transits=transits,
        expenses=expenses,
    )


def _should_prefer_area_for_broad_walk(geo_context: dict[str, object]) -> bool:
    if not geo_context.get("is_broad_walking_cluster"):
        return False
    if not geo_context.get("area_name"):
        return False
    category = str(geo_context.get("poi_category", "") or "")
    poi_type = str(geo_context.get("poi_type", "") or "")
    if category == "shop":
        return True
    return (category, poi_type) in MINOR_WALKING_POI_TYPES


def _should_prefer_area_for_airport_terminal(geo_context: dict[str, object]) -> bool:
    if not geo_context.get("is_airport"):
        return False
    if geo_context.get("airport_name"):
        return False
    if not geo_context.get("area_name"):
        return False
    return (
        str(geo_context.get("poi_category", "") or "") == "aeroway"
        and str(geo_context.get("poi_type", "") or "") in {"terminal", "gate"}
    )
