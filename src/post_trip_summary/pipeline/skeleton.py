"""Build trip skeleton from clustered photos and supplementary data."""
from datetime import date, datetime, timedelta
from collections import defaultdict

from geopy.distance import geodesic

from post_trip_summary.models import (
    Trip, Day, Event, Photo, Location, Accommodation, Transit, Expense,
)
from post_trip_summary.geo.clustering import build_clusters
from post_trip_summary.geo.reverse_geocode import reverse_geocode


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
        if acc.check_in <= cluster_date <= acc.check_out:
            dist = geodesic(centroid, (acc.location.lat, acc.location.lon)).meters
            if dist < 500:
                return {"name": acc.name, "type": "hotel", "source": "itinerary", "location": acc.location}

    # Check activities
    for act in activities:
        act_date = date.fromisoformat(act["date"]) if isinstance(act["date"], str) else act["date"]
        if act_date == cluster_date:
            return {"name": act["name"], "type": "activity", "source": "itinerary"}

    return None


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

    # Cluster photos
    clusters = build_clusters(photos, gap_minutes, distance_meters)

    # Determine date range
    all_dates = set()
    for c in clusters:
        all_dates.add(c["time_range"][0].date())
        all_dates.add(c["time_range"][1].date())
    for acc in accommodations:
        d = acc.check_in
        while d <= acc.check_out:
            all_dates.add(d)
            d += timedelta(days=1)

    if not all_dates:
        return Trip(name="", date_range=(date.today(), date.today()))

    date_range = (min(all_dates), max(all_dates))

    # Build events from clusters
    events_by_date: dict[date, list[Event]] = defaultdict(list)

    for cluster in clusters:
        c_date = cluster["time_range"][0].date()
        centroid = cluster["centroid"]

        # Cross-reference
        itinerary_match = _match_cluster_to_itinerary(cluster, accommodations, activities)
        expense_match = _match_cluster_to_expense(cluster, expenses)
        google_match = _match_cluster_to_google_maps(cluster, place_visits)

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

        if google_match:
            name = google_match.get("name", "")
            sources.append("google_maps")
        if itinerary_match:
            name = name or itinerary_match.get("name", "")
            event_type = itinerary_match.get("type", "unknown")
            sources.append("itinerary")
        if expense_match:
            if not name:
                name = expense_match.merchant
            if event_type == "unknown":
                event_type = _classify_event(expense_category=expense_match.category)
            sources.append("credit_card")

        if event_type == "unknown":
            event_type = _classify_event(itinerary_match, expense_match.category if expense_match else None, google_match)

        # Build location
        if centroid:
            geo = reverse_geocode(centroid[0], centroid[1])
            location = Location(
                lat=centroid[0], lon=centroid[1],
                name=name or geo.get("city", ""),
                address=None,
                city=geo.get("city", ""),
                country=geo.get("country", ""),
            )
        else:
            location = Location(lat=0, lon=0, name=name, address=None, city="", country="")

        event = Event(
            id="",
            type=event_type,
            name=name or location.city or "Unknown",
            time_range=cluster["time_range"],
            location=location,
            photos=cluster["photos"],
            description="",
            notes="",
            sources=sources,
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
