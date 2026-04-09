"""Tests for montage-based enrichment pipeline."""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image
from post_trip_summary.models import Trip, Day, Event, Photo, Location


def _location():
    return Location(lat=0, lon=0, name="Test", address=None, city="Test", country="NZ")


def _photo(tmp_path, name, minutes=0):
    path = tmp_path / f"{name}.jpg"
    Image.new("RGB", (100, 100), "red").save(path, "JPEG")
    return Photo(path=path, timestamp=datetime(2026, 1, 1, 10, minutes), gps=None)


def _trip_with_event(tmp_path, photo_count):
    photos = [_photo(tmp_path, f"p{i}", i) for i in range(photo_count)]
    event = Event(
        id="d01-e01", type="landmark", name="Hobbiton",
        time_range=(photos[0].timestamp, photos[-1].timestamp),
        location=_location(), photos=photos,
    )
    return Trip(
        name="Test", date_range=(datetime(2026, 1, 1).date(), datetime(2026, 1, 1).date()),
        days=[Day(date=datetime(2026, 1, 1).date(), events=[event])],
    )


class TestQuickMode:
    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_montage_sent_for_event_with_many_photos(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {"summary": "Toured the Hobbiton movie set.", "highlights": [1, 3, 5]}
        mock_create.return_value = mock_provider
        trip = _trip_with_event(tmp_path, photo_count=10)
        result = enrich_trip_headless(trip, mode="quick")
        event = result.days[0].events[0]
        assert event.summary == "Toured the Hobbiton movie set."
        assert event.description == "Toured the Hobbiton movie set."
        mock_provider.analyze_montage.assert_called_once()

    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_highlights_from_montage_picks(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {"summary": "A tour.", "highlights": [2, 4]}
        mock_create.return_value = mock_provider
        trip = _trip_with_event(tmp_path, photo_count=6)
        result = enrich_trip_headless(trip, mode="quick")
        event = result.days[0].events[0]
        highlighted = [p for p in event.photos if p.is_highlight]
        assert len(highlighted) == 2

    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_few_photos_skip_montage(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze.return_value = MagicMock(description="A single photo.", landmark=None, confidence="medium")
        mock_create.return_value = mock_provider
        trip = _trip_with_event(tmp_path, photo_count=2)
        result = enrich_trip_headless(trip, mode="quick")
        mock_provider.analyze_montage.assert_not_called()
        assert mock_provider.analyze.call_count >= 1


class TestSkipMode:
    def test_skip_mode_selects_highlights_only(self, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        trip = _trip_with_event(tmp_path, photo_count=6)
        result = enrich_trip_headless(trip, mode="skip")
        event = result.days[0].events[0]
        assert event.summary == ""
        assert event.description == ""
        highlighted = [p for p in event.photos if p.is_highlight]
        assert len(highlighted) > 0
