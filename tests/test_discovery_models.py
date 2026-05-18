from pathlib import Path

import pytest

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.serialization import (
    decode_vacation_blend,
    encode_vacation_blend,
    load_vacation_blend,
    save_vacation_blend,
)
from post_trip_summary.discovery.taxonomy import THEME_BY_ID, validate_theme_ids


def test_taxonomy_has_expected_theme_ids():
    expected = {
        "road_trip",
        "adventure_outdoors",
        "nature_wildlife",
        "culture_sightseeing",
        "food_drink",
        "people_social",
        "nightlife_events",
        "beach_relaxation",
        "resort_luxury",
        "family_milestone",
    }

    assert set(THEME_BY_ID) == expected
    assert THEME_BY_ID["road_trip"].label == "Road Trip"
    assert THEME_BY_ID["beach_relaxation"].label == "Beach & Relaxation"


def test_validate_theme_ids_rejects_unknown():
    with pytest.raises(ValueError, match="unknown theme id"):
        validate_theme_ids(["road_trip", "made_up_theme"])


def test_vacation_blend_round_trips_json(tmp_path):
    blend = VacationBlend(
        primary_themes=["road_trip", "adventure_outdoors"],
        secondary_themes=["food_drink"],
        rejected_themes=["nightlife_events"],
        confidence="high",
        evidence=["Many location changes", "Outdoor place names"],
        theme_scores=[
            ThemeScore(
                theme_id="road_trip",
                score=82.5,
                confidence="high",
                evidence=["Travel across 8 cities"],
                sources=["metadata"],
            )
        ],
        analysis_mode="metadata_only",
        sample_size=0,
        estimated_cost=0.0,
        warnings=["Local AI disabled"],
    )

    encoded = encode_vacation_blend(blend)
    decoded = decode_vacation_blend(encoded)

    assert decoded == blend

    path = tmp_path / "vacation_blend.json"
    save_vacation_blend(path, blend)
    loaded = load_vacation_blend(path)

    assert loaded == blend
