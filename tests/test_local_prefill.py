from datetime import date, datetime, timedelta
from pathlib import Path

from post_trip_summary.models import Day, Event, Location, Photo, Trip
from post_trip_summary.vision.client import VisionResult


class FakeProvider:
    def __init__(self, descriptions=None, fail_at=None, synthesis="Synthesized local summary."):
        self.descriptions = list(descriptions or [])
        self.fail_at = fail_at
        self.synthesis = synthesis
        self.analyze_calls = []
        self.synthesize_calls = []

    def analyze(self, image_data, media_type="image/jpeg", purpose="scene", context=""):
        self.analyze_calls.append((image_data, media_type, purpose, context))
        if self.fail_at == len(self.analyze_calls):
            raise RuntimeError("local model failed")
        description = self.descriptions.pop(0) if self.descriptions else f"Description {len(self.analyze_calls)}"
        return VisionResult(description=description, confidence="medium")

    def synthesize(self, prompt):
        self.synthesize_calls.append(prompt)
        return self.synthesis


def _photo(tmp_path: Path, name: str, minutes: int = 0, description: str | None = None) -> Photo:
    path = tmp_path / f"{name}.jpg"
    path.write_bytes(b"fake-image")
    return Photo(
        path=path,
        timestamp=datetime(2026, 3, 5, 10, 0) + timedelta(minutes=minutes),
        gps=(48.858, 2.294),
        ai_description=description,
    )


def _trip_with_photos(tmp_path: Path, photos: list[Photo]) -> Trip:
    event = Event(
        id="day01-event01",
        type="landmark",
        name="Eiffel Tower",
        time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 11, 0)),
        location=Location(
            lat=48.858,
            lon=2.294,
            name="Eiffel Tower",
            address=None,
            city="Paris",
            country="France",
        ),
        photos=photos,
    )
    return Trip(
        name="Paris 2026",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[Day(date=date(2026, 3, 5), events=[event])],
    )


def test_prefill_describes_representative_photos_and_writes_summary(tmp_path):
    from post_trip_summary.pipeline.local_prefill import prefill_trip_with_local_descriptions

    photos = [_photo(tmp_path, f"p{i}", i) for i in range(3)]
    trip = _trip_with_photos(tmp_path, photos)
    provider = FakeProvider(descriptions=["First local description.", "Second local description."])

    stats = prefill_trip_with_local_descriptions(
        trip,
        provider=provider,
        max_photos_per_event=2,
    )

    event = trip.days[0].events[0]
    assert photos[0].ai_description == "First local description."
    assert photos[1].ai_description == "Second local description."
    assert photos[2].ai_description is None
    assert event.summary == "Synthesized local summary."
    assert event.description == "Synthesized local summary."
    assert [p.is_highlight for p in photos] == [True, True, False]
    assert stats.events_seen == 1
    assert stats.photos_attempted == 2
    assert stats.photos_described == 2
    assert stats.summaries_written == 1


def test_prefill_skips_existing_descriptions_by_default(tmp_path):
    from post_trip_summary.pipeline.local_prefill import prefill_trip_with_local_descriptions

    photos = [
        _photo(tmp_path, "p0", 0, description="Already described."),
        _photo(tmp_path, "p1", 1),
    ]
    trip = _trip_with_photos(tmp_path, photos)
    provider = FakeProvider(descriptions=["New second description."])

    stats = prefill_trip_with_local_descriptions(trip, provider=provider, max_photos_per_event=2)

    assert photos[0].ai_description == "Already described."
    assert photos[1].ai_description == "New second description."
    assert len(provider.analyze_calls) == 1
    assert stats.skipped_existing == 1


def test_prefill_overwrite_replaces_existing_descriptions(tmp_path):
    from post_trip_summary.pipeline.local_prefill import prefill_trip_with_local_descriptions

    photos = [_photo(tmp_path, "p0", description="Old description.")]
    trip = _trip_with_photos(tmp_path, photos)
    provider = FakeProvider(descriptions=["Replacement description."])

    stats = prefill_trip_with_local_descriptions(
        trip,
        provider=provider,
        max_photos_per_event=1,
        overwrite=True,
    )

    assert photos[0].ai_description == "Replacement description."
    assert stats.skipped_existing == 0
    assert stats.photos_described == 1


def test_prefill_counts_failures_and_continues(tmp_path):
    from post_trip_summary.pipeline.local_prefill import prefill_trip_with_local_descriptions

    photos = [_photo(tmp_path, "p0"), _photo(tmp_path, "p1", 1)]
    trip = _trip_with_photos(tmp_path, photos)
    provider = FakeProvider(descriptions=["Second works."], fail_at=1)

    stats = prefill_trip_with_local_descriptions(trip, provider=provider, max_photos_per_event=2)

    assert photos[0].ai_description is None
    assert photos[1].ai_description == "Second works."
    assert stats.failed == 1
    assert stats.photos_described == 1


def test_prefill_progress_callback_reports_events(tmp_path):
    from post_trip_summary.pipeline.local_prefill import prefill_trip_with_local_descriptions

    photos = [_photo(tmp_path, "p0")]
    trip = _trip_with_photos(tmp_path, photos)
    provider = FakeProvider(descriptions=["One local description."])
    calls = []

    prefill_trip_with_local_descriptions(
        trip,
        provider=provider,
        progress_callback=lambda phase, current, total, label="": calls.append((phase, current, total, label)),
    )

    assert calls[0] == ("local_prefill", 1, 1, "Eiffel Tower")
    assert calls[-1] == ("done", 1, 1, "Local prefill complete")


def test_prefill_default_provider_uses_ollama_settings(monkeypatch, tmp_path):
    from post_trip_summary.pipeline import local_prefill

    photos = [_photo(tmp_path, "p0")]
    trip = _trip_with_photos(tmp_path, photos)
    provider = FakeProvider(descriptions=["Local default provider."])
    created = {}

    def fake_create_provider(name, model=None, base_url=None, timeout_seconds=None, **kwargs):
        created.update({
            "name": name,
            "model": model,
            "base_url": base_url,
            "timeout_seconds": timeout_seconds,
        })
        return provider

    monkeypatch.setattr(local_prefill, "load_settings", lambda: {
        "vision": {
            "ollama_model": "gemma4:e2b",
            "ollama_base_url": "http://localhost:11434",
            "ollama_timeout_seconds": 45,
        }
    })
    monkeypatch.setattr(local_prefill, "create_provider", fake_create_provider)

    local_prefill.prefill_trip_with_local_descriptions(trip)

    assert created == {
        "name": "ollama",
        "model": "gemma4:e2b",
        "base_url": "http://localhost:11434",
        "timeout_seconds": 45,
    }
