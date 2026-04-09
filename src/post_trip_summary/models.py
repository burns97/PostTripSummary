# src/post_trip_summary/models.py
"""Core data models for trip representation."""
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


@dataclass
class Location:
    lat: float
    lon: float
    name: str
    address: str | None
    city: str
    country: str


@dataclass
class Photo:
    path: Path
    timestamp: datetime
    gps: tuple[float, float] | None
    is_highlight: bool = False
    is_kept: bool = True
    quality_score: float | None = None  # 0-100 composite quality score
    ai_description: str | None = None


@dataclass
class Event:
    id: str
    type: str  # landmark, restaurant, hotel, activity, transit, unknown
    name: str
    time_range: tuple[datetime, datetime]
    location: Location
    photos: list[Photo] = field(default_factory=list)
    description: str = ""
    notes: str = ""
    sources: list[str] = field(default_factory=list)
    name_candidates: dict[str, str] = field(default_factory=dict)


@dataclass
class Day:
    date: date
    events: list[Event] = field(default_factory=list)


@dataclass
class TransitPoint:
    location: Location
    time: datetime
    name: str


@dataclass
class Transit:
    mode: str  # flight, car_rental, train, ferry, bus, taxi, walking
    departure: TransitPoint
    arrival: TransitPoint
    details: dict = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)


@dataclass
class Accommodation:
    name: str
    location: Location
    check_in: datetime
    check_out: datetime
    sources: list[str] = field(default_factory=list)


@dataclass
class Expense:
    date: date
    amount: float
    currency: str
    merchant: str
    category: str | None = None
    event_id: str | None = None
    source: str = ""


@dataclass
class Trip:
    name: str
    date_range: tuple[date, date]
    days: list[Day] = field(default_factory=list)
    accommodations: list[Accommodation] = field(default_factory=list)
    transits: list[Transit] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)
