# tests/test_enrich.py
from datetime import datetime, date
from pathlib import Path
from unittest.mock import patch, MagicMock
from post_trip_summary.models import Trip, Day, Event, Photo, Location
from post_trip_summary.vision.client import VisionResult
from post_trip_summary.pipeline.enrich import enrich_trip, _select_highlights


def _photo(name: str) -> Photo:
    return Photo(path=Path(f"/photos/{name}.jpg"), timestamp=datetime(2026, 3, 5, 16, 0), gps=(48.858, 2.294))


def _event(name: str, sources: list[str], num_photos: int = 10) -> Event:
    return Event(
        id="day01-event01", type="unknown", name=name,
        time_range=(datetime(2026, 3, 5, 16, 0), datetime(2026, 3, 5, 17, 0)),
        location=Location(lat=48.858, lon=2.294, name=name, address=None, city="Paris", country="France"),
        photos=[_photo(f"img{i}") for i in range(num_photos)],
        description="", notes="", sources=sources,
    )


def test_select_highlights_default():
    photos = [_photo(f"img{i}") for i in range(20)]
    highlights = _select_highlights(photos, max_count=5)
    assert len(highlights) == 5
    assert all(p.is_highlight for p in highlights)


def test_select_highlights_fewer_than_max():
    photos = [_photo(f"img{i}") for i in range(3)]
    highlights = _select_highlights(photos, max_count=5)
    assert len(highlights) == 3


def test_enrich_applies_vision_results():
    """Mock the vision client and verify enrichment updates events."""
    event = _event("Unknown Place", sources=["exif"], num_photos=3)
    trip = Trip(
        name="Test", date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )

    mock_result = VisionResult(description="The Eiffel Tower", landmark="Eiffel Tower", confidence="high")

    mock_provider = MagicMock()
    mock_provider.analyze.return_value = mock_result
    mock_provider.estimate_cost.return_value = 0.0
    mock_provider.synthesize.return_value = "The Eiffel Tower rises above the Paris skyline."

    with patch("post_trip_summary.pipeline.enrich.get_vision_settings", return_value={"provider": "gemini", "api_key": "test", "model": "gemini-2.0-flash"}), \
         patch("post_trip_summary.pipeline.enrich.create_provider", return_value=mock_provider), \
         patch("post_trip_summary.pipeline.enrich._read_image", return_value=(b"fakedata", "image/jpeg")):

        enriched = enrich_trip(trip, auto_approve=True)
        # With 3 photos all getting descriptions, synthesis replaces the pass-1 description
        assert enriched.days[0].events[0].description == "The Eiffel Tower rises above the Paris skyline."


def _trip_with_event(event):
    return Trip(
        name="Test", date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )


def _enrich_patches(mock_provider):
    return (
        patch("post_trip_summary.pipeline.enrich.get_vision_settings",
              return_value={"provider": "gemini", "api_key": "test", "model": "gemini-2.0-flash"}),
        patch("post_trip_summary.pipeline.enrich.create_provider", return_value=mock_provider),
        patch("post_trip_summary.pipeline.enrich._read_image", return_value=(b"fakedata", "image/jpeg")),
    )


def test_synthesis_called_for_multi_highlight_events():
    """Synthesize is called when an event has 2+ described highlights."""
    event = _event("Eiffel Tower", sources=["exif"], num_photos=3)
    trip = _trip_with_event(event)

    mock_result = VisionResult(description="A view of the tower", landmark="Eiffel Tower", confidence="high")

    mock_provider = MagicMock()
    mock_provider.analyze.return_value = mock_result
    mock_provider.estimate_cost.return_value = 0.0
    mock_provider.synthesize.return_value = "We visited the Eiffel Tower and enjoyed panoramic views of Paris."

    p1, p2, p3 = _enrich_patches(mock_provider)
    with p1, p2, p3:
        enriched = enrich_trip(trip, auto_approve=True)

    mock_provider.synthesize.assert_called_once()
    assert enriched.days[0].events[0].description == "We visited the Eiffel Tower and enjoyed panoramic views of Paris."


def test_synthesis_skipped_for_single_highlight():
    """Synthesize is NOT called when an event has only 1 highlight."""
    event = _event("Eiffel Tower", sources=["exif"], num_photos=1)
    trip = _trip_with_event(event)

    mock_result = VisionResult(description="A view of the tower", confidence="high")

    mock_provider = MagicMock()
    mock_provider.analyze.return_value = mock_result
    mock_provider.estimate_cost.return_value = 0.0

    p1, p2, p3 = _enrich_patches(mock_provider)
    with p1, p2, p3:
        enrich_trip(trip, auto_approve=True)

    mock_provider.synthesize.assert_not_called()


def test_synthesis_failure_keeps_original_description():
    """If synthesize raises, the pass-1 description is kept."""
    event = _event("Eiffel Tower", sources=["exif"], num_photos=3)
    trip = _trip_with_event(event)

    mock_result = VisionResult(description="A view of the tower", confidence="high")

    mock_provider = MagicMock()
    mock_provider.analyze.return_value = mock_result
    mock_provider.estimate_cost.return_value = 0.0
    mock_provider.synthesize.side_effect = RuntimeError("API error")

    p1, p2, p3 = _enrich_patches(mock_provider)
    with p1, p2, p3:
        enriched = enrich_trip(trip, auto_approve=True)

    # Pass-1 description should be preserved
    assert enriched.days[0].events[0].description == "A view of the tower"
