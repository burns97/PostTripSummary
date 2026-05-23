"""Local airport resolution for travel-logistics photo clusters."""
from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Iterable

from geopy.distance import geodesic

from post_trip_summary.settings import get_geocoding_settings

logger = logging.getLogger(__name__)

AIRPORT_SIGNAL_RADIUS_M = 10_000.0
AIRPORT_STRICT_RADIUS_M = 1_200.0
TRAVEL_AIRPORT_TYPES = {"large_airport", "medium_airport"}
AIRPORT_SIGNAL_TERMS = ("airport", "airfield", "aerodrome", "terminal", "gate")


@dataclass(frozen=True)
class Airport:
    ident: str
    type: str
    name: str
    lat: float
    lon: float
    country: str
    municipality: str
    scheduled_service: bool
    gps_code: str
    iata_code: str
    local_code: str
    source: str

    @property
    def display_name(self) -> str:
        if self.iata_code:
            return f"{self.name} ({self.iata_code})"
        return self.name


def resolve_airport_candidate(
    lat: float,
    lon: float,
    geo_context: dict[str, object] | None = None,
    *,
    airports: Iterable[Airport] | None = None,
) -> dict[str, object] | None:
    """Return the nearest plausible travel airport for an event coordinate."""
    settings = get_geocoding_settings()
    if not settings.get("airport_lookup_enabled", True):
        return None

    airport_list = tuple(airports) if airports is not None else load_airports(settings.get("airports_csv_path"))
    if not airport_list:
        return None

    radius_m = AIRPORT_SIGNAL_RADIUS_M if _has_airport_context(geo_context) else AIRPORT_STRICT_RADIUS_M
    candidates: list[tuple[float, Airport]] = []
    for airport in airport_list:
        if not _is_travel_airport(airport):
            continue
        distance_m = geodesic((lat, lon), (airport.lat, airport.lon)).meters
        if distance_m <= radius_m:
            candidates.append((distance_m, airport))

    if not candidates:
        return None

    distance_m, airport = min(candidates, key=lambda item: (item[0], _type_priority(item[1].type)))
    return {
        "name": airport.name,
        "display_name": airport.display_name,
        "iata_code": airport.iata_code,
        "icao_code": airport.gps_code or airport.ident,
        "type": airport.type,
        "municipality": airport.municipality,
        "country": airport.country,
        "lat": airport.lat,
        "lon": airport.lon,
        "distance_m": round(distance_m, 1),
        "source": airport.source,
    }


def load_airports(airports_csv_path: str | Path | None = None) -> tuple[Airport, ...]:
    """Load bundled seed airports plus an optional OurAirports-compatible CSV."""
    custom_path = _settings_or_env_airports_path(airports_csv_path)
    return _load_airports_cached(str(custom_path or ""))


@lru_cache(maxsize=8)
def _load_airports_cached(custom_path: str) -> tuple[Airport, ...]:
    airports = list(_load_seed_airports())
    if custom_path:
        path = Path(custom_path).expanduser()
        if path.exists():
            airports.extend(_load_airports_csv(path, source=str(path)))
        else:
            logger.warning("Configured airports CSV does not exist: %s", path)
    return tuple(_dedupe_airports(airports))


def _load_seed_airports() -> tuple[Airport, ...]:
    resource = files("post_trip_summary").joinpath("data/airports_seed.csv")
    with resource.open("r", encoding="utf-8", newline="") as handle:
        return tuple(_parse_airport_rows(csv.DictReader(handle), source="airport_seed"))


def _load_airports_csv(path: Path, source: str) -> tuple[Airport, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return tuple(_parse_airport_rows(csv.DictReader(handle), source=source))


def _parse_airport_rows(rows: Iterable[dict[str, str]], source: str) -> Iterable[Airport]:
    for row in rows:
        try:
            lat = float(row.get("latitude_deg", "") or row.get("lat", ""))
            lon = float(row.get("longitude_deg", "") or row.get("lon", ""))
        except ValueError:
            continue
        airport_type = row.get("type", "")
        if airport_type in {"closed", "heliport", "seaplane_base", "balloonport"}:
            continue
        yield Airport(
            ident=row.get("ident", "") or row.get("gps_code", ""),
            type=airport_type,
            name=row.get("name", ""),
            lat=lat,
            lon=lon,
            country=row.get("iso_country", "") or row.get("country", ""),
            municipality=row.get("municipality", ""),
            scheduled_service=(row.get("scheduled_service", "").lower() == "yes"),
            gps_code=row.get("gps_code", ""),
            iata_code=row.get("iata_code", ""),
            local_code=row.get("local_code", ""),
            source=source,
        )


def _dedupe_airports(airports: Iterable[Airport]) -> list[Airport]:
    by_key: dict[tuple[str, str, str], Airport] = {}
    for airport in airports:
        key = (
            airport.iata_code.casefold(),
            airport.gps_code.casefold(),
            airport.name.casefold(),
        )
        by_key[key] = airport
    return list(by_key.values())


def _settings_or_env_airports_path(value: str | Path | None) -> Path | None:
    path_value = value or os.environ.get("POST_TRIP_SUMMARY_AIRPORTS_CSV", "")
    if not path_value:
        return None
    return Path(path_value)


def _has_airport_context(geo_context: dict[str, object] | None) -> bool:
    if not geo_context:
        return False
    if geo_context.get("is_airport"):
        return True
    values = [
        geo_context.get("place_name"),
        geo_context.get("poi_name"),
        geo_context.get("poi_category"),
        geo_context.get("poi_type"),
        geo_context.get("airport_name"),
    ]
    text = " ".join(str(value).lower() for value in values if value)
    return any(term in text for term in AIRPORT_SIGNAL_TERMS)


def _is_travel_airport(airport: Airport) -> bool:
    return airport.type in TRAVEL_AIRPORT_TYPES or airport.scheduled_service


def _type_priority(airport_type: str) -> int:
    priorities = {
        "large_airport": 0,
        "medium_airport": 1,
        "small_airport": 2,
    }
    return priorities.get(airport_type, 3)
