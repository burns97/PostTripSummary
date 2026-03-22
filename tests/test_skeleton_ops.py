# tests/test_skeleton_ops.py
"""Tests for skeleton editing operations."""
from datetime import date, datetime

import pytest

from post_trip_summary.models import Day, Event, Location, Photo
from post_trip_summary.pipeline.skeleton_ops import (
    merge_events, suggest_merge_name, rename_event,
    delete_event, change_event_type, set_event_note,
)


def _loc():
    return Location(lat=-36.8, lon=174.7, name="Test", address=None, city="Auckland", country="NZ")


def _photo(name="img.jpg"):
    from pathlib import Path
    return Photo(path=Path(name), timestamp=datetime(2025, 3, 15, 10, 0), gps=None)


def _event(eid, name="Place", photos=None, sources=None, notes="",
           start_h=10, end_h=11):
    return Event(
        id=eid, type="landmark", name=name,
        time_range=(datetime(2025, 3, 15, start_h, 0), datetime(2025, 3, 15, end_h, 0)),
        location=_loc(),
        photos=photos or [],
        sources=sources or ["exif"],
        notes=notes,
    )


def _day(events):
    return Day(date=date(2025, 3, 15), events=events)


class TestMergeEvents:
    def test_combines_photos(self):
        e1 = _event("e1", photos=[_photo("a.jpg"), _photo("b.jpg")])
        e2 = _event("e2", photos=[_photo("c.jpg"), _photo("d.jpg"), _photo("e.jpg")])
        e3 = _event("e3", photos=[_photo("f.jpg")])
        day = _day([e1, e2, e3])

        merged = merge_events(day, ["e1", "e2", "e3"])
        assert len(merged.photos) == 6

    def test_extends_time_range(self):
        e1 = _event("e1", start_h=9, end_h=10)
        e2 = _event("e2", start_h=10, end_h=11)
        e3 = _event("e3", start_h=11, end_h=14)
        day = _day([e1, e2, e3])

        merged = merge_events(day, ["e1", "e2", "e3"])
        assert merged.time_range[0].hour == 9
        assert merged.time_range[1].hour == 14

    def test_unions_sources(self):
        e1 = _event("e1", sources=["exif", "google_maps"])
        e2 = _event("e2", sources=["exif", "itinerary"])
        day = _day([e1, e2])

        merged = merge_events(day, ["e1", "e2"])
        assert set(merged.sources) == {"exif", "google_maps", "itinerary"}

    def test_concatenates_notes(self):
        e1 = _event("e1", notes="First note")
        e2 = _event("e2", notes="Second note")
        e3 = _event("e3", notes="")
        day = _day([e1, e2, e3])

        merged = merge_events(day, ["e1", "e2", "e3"])
        assert merged.notes == "First note Second note"

    def test_splices_day(self):
        e1 = _event("e1")
        e2 = _event("e2")
        e3 = _event("e3")
        e4 = _event("e4")
        day = _day([e1, e2, e3, e4])

        merge_events(day, ["e2", "e3"])
        assert len(day.events) == 3
        assert day.events[0].id == "e1"
        assert day.events[1].id == "e2"  # merged
        assert day.events[2].id == "e4"

    def test_invalid_event_id(self):
        day = _day([_event("e1")])
        with pytest.raises(ValueError, match="not found"):
            merge_events(day, ["e1", "nonexistent"])


class TestSuggestMergeName:
    def test_skips_unknown(self):
        events = [
            _event("e1", name="Unknown"),
            _event("e2", name="Hobbiton"),
            _event("e3", name="Matamata"),
        ]
        assert suggest_merge_name(events) == "Hobbiton, Matamata"

    def test_all_unknown_uses_first(self):
        events = [_event("e1", name="Unknown"), _event("e2", name="Unknown")]
        assert suggest_merge_name(events) == "Unknown"

    def test_deduplicates(self):
        events = [_event("e1", name="Cafe"), _event("e2", name="Cafe")]
        assert suggest_merge_name(events) == "Cafe"


def test_rename_event():
    ev = _event("e1", name="Old Name")
    rename_event(ev, "New Name")
    assert ev.name == "New Name"


class TestDeleteEvent:
    def test_removes_from_day(self):
        e1, e2, e3 = _event("e1"), _event("e2"), _event("e3")
        day = _day([e1, e2, e3])
        removed = delete_event(day, "e2")
        assert removed.id == "e2"
        assert len(day.events) == 2
        assert all(e.id != "e2" for e in day.events)

    def test_invalid_id_raises(self):
        day = _day([_event("e1")])
        with pytest.raises(ValueError, match="not found"):
            delete_event(day, "nonexistent")


class TestChangeType:
    def test_valid_type(self):
        ev = _event("e1")
        change_event_type(ev, "restaurant")
        assert ev.type == "restaurant"

    def test_invalid_type_raises(self):
        ev = _event("e1")
        with pytest.raises(ValueError, match="Invalid type"):
            change_event_type(ev, "beach")


def test_set_event_note():
    ev = _event("e1", notes="")
    set_event_note(ev, "Great gelato spot")
    assert ev.notes == "Great gelato spot"
