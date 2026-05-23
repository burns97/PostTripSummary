from datetime import date, datetime
from pathlib import Path

from post_trip_summary.models import Day, Event, Location, Photo, Trip


def _photo(
    name: str,
    *,
    day: int = 5,
    hour: int = 10,
    is_highlight: bool = False,
    is_kept: bool = True,
    quality_score: float | None = None,
) -> Photo:
    return Photo(
        path=Path(f"/photos/{name}.jpg"),
        timestamp=datetime(2026, 3, day, hour, 0),
        gps=(48.858, 2.294),
        is_highlight=is_highlight,
        is_kept=is_kept,
        quality_score=quality_score,
        ai_description=f"{name} description",
    )


def _event(
    event_id: str,
    name: str,
    city: str,
    country: str,
    photos: list[Photo],
    *,
    description: str = "A memorable stop.",
    event_type: str = "landmark",
    lat: float = 48.858,
    lon: float = 2.294,
) -> Event:
    loc = Location(
        lat=lat,
        lon=lon,
        name=name,
        address=None,
        city=city,
        country=country,
    )
    return Event(
        id=event_id,
        type=event_type,
        name=name,
        time_range=(datetime(2026, 3, 5, 10, 0), datetime(2026, 3, 5, 11, 0)),
        location=loc,
        photos=photos,
        description=description,
        notes="",
        sources=["exif"],
    )


def _trip() -> Trip:
    day1 = Day(
        date=date(2026, 3, 5),
        events=[
            _event(
                "day01-event01",
                "Eiffel Tower",
                "Paris",
                "France",
                [
                    _photo("low-highlight", is_highlight=True, quality_score=40),
                    _photo("best-highlight", is_highlight=True, quality_score=95),
                    _photo("removed-highlight", is_highlight=True, is_kept=False, quality_score=100),
                ],
            )
        ],
    )
    day2 = Day(
        date=date(2026, 3, 6),
        events=[
            _event(
                "day02-event01",
                "Louvre",
                "Paris",
                "France",
                [_photo("louvre", day=6, is_highlight=False, quality_score=80)],
            )
        ],
    )
    return Trip(
        name="Paris 2026",
        date_range=(date(2026, 3, 5), date(2026, 3, 6)),
        days=[day1, day2],
    )


def test_select_cover_photo_prefers_highest_quality_kept_highlight():
    from post_trip_summary.output.trip_story import select_cover_photo

    cover = select_cover_photo(_trip())

    assert cover is not None
    assert cover.path.name == "best-highlight.jpg"


def test_select_cover_photo_falls_back_to_first_kept_photo_when_no_highlights():
    from post_trip_summary.output.trip_story import select_cover_photo

    trip = Trip(
        name="Fallback",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[
            Day(
                date=date(2026, 3, 5),
                events=[
                    _event(
                        "day01-event01",
                        "Walk",
                        "Paris",
                        "France",
                        [_photo("first-kept", is_highlight=False)],
                    )
                ],
            )
        ],
    )

    cover = select_cover_photo(trip)

    assert cover is not None
    assert cover.path.name == "first-kept.jpg"


def test_compute_story_stats_counts_kept_photos_and_locations():
    from post_trip_summary.output.trip_story import compute_story_stats

    stats = compute_story_stats(_trip())

    assert stats == {
        "days": 2,
        "stops": 2,
        "photos": 3,
        "highlights": 2,
        "cities": 1,
        "countries": 1,
    }


def test_location_summary_uses_ordered_unique_locations():
    from post_trip_summary.output.trip_story import build_location_summary

    assert build_location_summary(_trip()) == "Paris, France"


def test_location_summary_ignores_transit_location_noise():
    from post_trip_summary.output.trip_story import build_location_summary, compute_story_stats

    trip = Trip(
        name="New Zealand 2026",
        date_range=(date(2026, 2, 18), date(2026, 3, 6)),
        days=[
            Day(
                date=date(2026, 2, 18),
                events=[
                    _event(
                        "day01-event01",
                        "John Glenn Columbus International Airport",
                        "Columbus",
                        "US",
                        [_photo("cmh", day=18)],
                        event_type="transit",
                        lat=39.9999,
                        lon=-82.8872,
                    ),
                    _event(
                        "day01-event02",
                        "DFW to AKL",
                        "Otu",
                        "NG",
                        [_photo("long-haul", day=18)],
                        event_type="transit",
                        lat=6.69,
                        lon=4.90,
                    ),
                    _event(
                        "day02-event01",
                        "Auckland Central",
                        "Auckland",
                        "NZ",
                        [_photo("auckland", day=19)],
                        lat=-36.8485,
                        lon=174.7633,
                    ),
                ],
            )
        ],
    )

    assert build_location_summary(trip) == "Auckland, NZ"
    stats = compute_story_stats(trip)
    assert stats["cities"] == 1
    assert stats["countries"] == 1


def test_select_highlight_photos_returns_kept_highlights_only():
    from post_trip_summary.output.trip_story import select_highlight_photos

    photos = select_highlight_photos(_trip())

    assert [p.path.name for p in photos] == ["low-highlight.jpg", "best-highlight.jpg"]


def test_generate_trip_story_writes_editorial_html(tmp_path):
    from post_trip_summary.output.trip_story import generate_trip_story

    output_path = tmp_path / "trip-story.html"
    generate_trip_story(_trip(), output_path, map_image="route-map.png")

    html = output_path.read_text(encoding="utf-8")
    assert output_path.exists()
    assert "Paris 2026" in html
    assert "Paris, France" in html
    assert "route-map.png" in html
    assert "Eiffel Tower" in html
    assert "By the Numbers" in html
    assert "best-highlight.jpg" in html
    assert "Trip Story" in html


def test_generate_trip_story_escapes_user_and_ai_content(tmp_path):
    from post_trip_summary.output.trip_story import generate_trip_story

    malicious = "<script>alert(1)</script>"
    trip = Trip(
        name=f"Paris {malicious}",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[
            Day(
                date=date(2026, 3, 5),
                events=[
                    _event(
                        "day01-event01",
                        f"Tower {malicious}",
                        f"City {malicious}",
                        "France",
                        [
                            _photo(
                                "cover",
                                is_highlight=True,
                                quality_score=100,
                            ),
                        ],
                        description=f"Description {malicious}",
                    )
                ],
            )
        ],
    )
    trip.days[0].events[0].notes = f"Note {malicious}"
    trip.days[0].events[0].photos[0].ai_description = f"Alt {malicious}"
    output_path = tmp_path / "trip-story.html"

    generate_trip_story(trip, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "Paris &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Tower &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Description &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Note &lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'alt="Alt &lt;script&gt;alert(1)&lt;/script&gt;"' in html


def test_generate_trip_story_uses_img_for_cover_photo_with_apostrophe(tmp_path):
    from post_trip_summary.output.trip_story import generate_trip_story

    trip = Trip(
        name="Paris 2026",
        date_range=(date(2026, 3, 5), date(2026, 3, 5)),
        days=[
            Day(
                date=date(2026, 3, 5),
                events=[
                    _event(
                        "day01-event01",
                        "Eiffel Tower",
                        "Paris",
                        "France",
                        [
                            _photo("Karen's favorite", is_highlight=True, quality_score=100),
                        ],
                    )
                ],
            )
        ],
    )
    output_path = tmp_path / "trip-story.html"

    generate_trip_story(trip, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "background-image" not in html
    assert '<img class="hero-cover" src="photos/Karen&#39;s favorite.jpg"' in html
    assert "Trip Story" in html
