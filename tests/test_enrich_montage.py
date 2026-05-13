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
    def test_few_photos_use_batch_montage(self, mock_settings, mock_create, tmp_path):
        """Small events (<=3 photos) are now batched into a single montage call."""
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {
            "photos": {
                "1": {"description": "Photo one.", "landmark": None, "text_found": None},
                "2": {"description": "Photo two.", "landmark": None, "text_found": None},
            }
        }
        mock_create.return_value = mock_provider
        trip = _trip_with_event(tmp_path, photo_count=2)
        result = enrich_trip_headless(trip, mode="quick")
        mock_provider.analyze_montage.assert_called_once()
        mock_provider.analyze.assert_not_called()
        event = result.days[0].events[0]
        assert event.photos[0].ai_description == "Photo one."
        assert event.photos[1].ai_description == "Photo two."
        assert all(p.is_highlight for p in event.photos)

    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_batch_fallback_to_individual(self, mock_settings, mock_create, tmp_path):
        """If batch montage fails, falls back to individual analyze calls."""
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        # First call (batch) raises, subsequent calls (individual fallback) succeed
        mock_provider.analyze_montage.side_effect = RuntimeError("API error")
        mock_provider.analyze.return_value = MagicMock(description="Fallback desc.", landmark=None, confidence="medium")
        mock_create.return_value = mock_provider
        trip = _trip_with_event(tmp_path, photo_count=2)
        result = enrich_trip_headless(trip, mode="quick")
        event = result.days[0].events[0]
        assert event.summary == "Fallback desc."
        assert mock_provider.analyze.call_count == 2


class TestThoroughMode:
    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_thorough_sends_individual_photos_after_montage(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {"summary": "Toured the set.", "highlights": [1, 3, 5]}
        mock_provider.analyze.return_value = MagicMock(description="A hobbit hole.", landmark=None, confidence="medium")
        mock_provider.synthesize.return_value = '{"narrative": "We walked through the magical Hobbiton set."}'
        mock_create.return_value = mock_provider
        trip = _trip_with_event(tmp_path, photo_count=10)
        result = enrich_trip_headless(trip, mode="thorough")
        event = result.days[0].events[0]
        assert event.summary == "Toured the set."
        # Individual analyze should have been called for highlights
        assert mock_provider.analyze.call_count >= 1

    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_thorough_calls_synthesize(self, mock_settings, mock_create, tmp_path):
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {"summary": "Toured the set.", "highlights": [1, 3]}
        mock_provider.analyze.return_value = MagicMock(description="A detailed scene.", landmark=None, confidence="medium")
        mock_provider.synthesize.return_value = '{"narrative": "A rich journal narrative."}'
        mock_create.return_value = mock_provider
        trip = _trip_with_event(tmp_path, photo_count=8)
        result = enrich_trip_headless(trip, mode="thorough")
        mock_provider.synthesize.assert_called_once()


class TestBatchGrouping:
    def test_batch_small_events_groups_correctly(self, tmp_path):
        from post_trip_summary.pipeline.enrich import _batch_small_events
        photos_2 = [_photo(tmp_path, f"a{i}", i) for i in range(2)]
        photos_3 = [_photo(tmp_path, f"b{i}", i) for i in range(3)]
        photos_6 = [_photo(tmp_path, f"c{i}", i) for i in range(6)]
        events = [
            Event(id="e1", type="landmark", name="Small1",
                  time_range=(photos_2[0].timestamp, photos_2[-1].timestamp),
                  location=_location(), photos=photos_2),
            Event(id="e2", type="landmark", name="Small2",
                  time_range=(photos_3[0].timestamp, photos_3[-1].timestamp),
                  location=_location(), photos=photos_3),
            Event(id="e3", type="landmark", name="Large",
                  time_range=(photos_6[0].timestamp, photos_6[-1].timestamp),
                  location=_location(), photos=photos_6),
        ]
        batches, large = _batch_small_events(events)
        assert len(batches) == 1
        assert len(batches[0]) == 2  # two small events in one batch
        assert len(large) == 1
        assert large[0].name == "Large"

    def test_batch_splits_at_max_photos(self, tmp_path):
        from post_trip_summary.pipeline.enrich import _batch_small_events
        # Create 8 events with 3 photos each = 24 photos total
        events = []
        for i in range(8):
            photos = [_photo(tmp_path, f"e{i}p{j}", j) for j in range(3)]
            events.append(Event(
                id=f"e{i}", type="landmark", name=f"Event{i}",
                time_range=(photos[0].timestamp, photos[-1].timestamp),
                location=_location(), photos=photos,
            ))
        batches, large = _batch_small_events(events, max_photos=20)
        assert len(large) == 0
        assert len(batches) == 2
        batch1_photos = sum(len(kept) for _, kept in batches[0])
        batch2_photos = sum(len(kept) for _, kept in batches[1])
        assert batch1_photos <= 20
        assert batch2_photos <= 20
        assert batch1_photos + batch2_photos == 24

    @patch("post_trip_summary.pipeline.enrich.create_provider")
    @patch("post_trip_summary.pipeline.enrich.get_vision_settings")
    def test_cross_event_batch_single_api_call(self, mock_settings, mock_create, tmp_path):
        """Multiple small events batched into one analyze_montage call."""
        from post_trip_summary.pipeline.enrich import enrich_trip_headless
        mock_settings.return_value = {"provider": "gemini", "api_key": "fake", "model": "gemini-2.5-flash"}
        mock_provider = MagicMock()
        mock_provider.analyze_montage.return_value = {
            "photos": {
                "1": {"description": "Event1 photo1.", "landmark": None, "text_found": None},
                "2": {"description": "Event1 photo2.", "landmark": None, "text_found": None},
                "3": {"description": "Event2 photo1.", "landmark": None, "text_found": None},
            }
        }
        mock_create.return_value = mock_provider

        photos1 = [_photo(tmp_path, "e1p0", 0), _photo(tmp_path, "e1p1", 1)]
        photos2 = [_photo(tmp_path, "e2p0", 5)]
        trip = Trip(
            name="Test", date_range=(datetime(2026, 1, 1).date(), datetime(2026, 1, 1).date()),
            days=[Day(date=datetime(2026, 1, 1).date(), events=[
                Event(id="e1", type="landmark", name="Place1",
                      time_range=(photos1[0].timestamp, photos1[-1].timestamp),
                      location=_location(), photos=photos1),
                Event(id="e2", type="landmark", name="Place2",
                      time_range=(photos2[0].timestamp, photos2[-1].timestamp),
                      location=_location(), photos=photos2),
            ])],
        )
        result = enrich_trip_headless(trip, mode="quick")
        # Single batch call for both small events
        assert mock_provider.analyze_montage.call_count == 1
        mock_provider.analyze.assert_not_called()
        e1 = result.days[0].events[0]
        e2 = result.days[0].events[1]
        assert e1.photos[0].ai_description == "Event1 photo1."
        assert e1.photos[1].ai_description == "Event1 photo2."
        assert e2.photos[0].ai_description == "Event2 photo1."
        assert e1.summary == "Event1 photo1."
        assert e2.summary == "Event2 photo1."


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
