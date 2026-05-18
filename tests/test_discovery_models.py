from dataclasses import fields

import pytest

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.serialization import (
    vacation_blend_from_dict,
    vacation_blend_to_dict,
)
import post_trip_summary.discovery.serialization as serialization
from post_trip_summary.discovery.taxonomy import (
    VACATION_THEMES,
    get_theme_label,
    validate_theme_ids,
)


def test_theme_score_has_exact_requested_fields():
    assert [field.name for field in fields(ThemeScore)] == [
        "theme_id",
        "label",
        "score",
        "evidence",
        "sample_event_ids",
    ]


def test_vacation_blend_has_exact_requested_fields():
    assert [field.name for field in fields(VacationBlend)] == [
        "analysis_mode",
        "confidence",
        "primary",
        "secondary",
        "rejected",
        "diagnostics",
        "warnings",
    ]


def test_taxonomy_has_expected_theme_ids_and_labels():
    expected = {
        "road_trip": "Road trip",
        "adventure_outdoors": "Adventure & outdoors",
        "culture_sightseeing": "Culture & sightseeing",
        "food_drink": "Food & drink",
        "beach_relaxation": "Beach & relaxation",
        "nightlife_events": "Nightlife & events",
        "family_friends": "Family & friends",
        "resort_luxury": "Resort & luxury",
        "shopping_city": "Shopping & city life",
        "wellness_slow": "Wellness & slow travel",
        "nature_wildlife": "Nature & wildlife",
    }

    assert {theme.id: theme.label for theme in VACATION_THEMES} == expected
    assert get_theme_label("road_trip") == "Road trip"
    assert get_theme_label("wellness_slow") == "Wellness & slow travel"
    assert get_theme_label("unexpected_theme") == "unexpected_theme"


def test_validate_theme_ids_rejects_unknown():
    with pytest.raises(ValueError, match="unknown theme id"):
        validate_theme_ids(["road_trip", "made_up_theme"])


def test_vacation_blend_round_trips_plain_dict():
    blend = VacationBlend(
        analysis_mode="metadata_only",
        confidence="high",
        primary=[
            ThemeScore(
                theme_id="road_trip",
                label="Road trip",
                score=82.5,
                evidence=["Travel across 8 cities"],
                sample_event_ids=["event-1", "event-2"],
            )
        ],
        secondary=[
            ThemeScore(
                theme_id="food_drink",
                label="Food & drink",
                score=45.0,
                evidence=["Several restaurant stops"],
                sample_event_ids=["event-3"],
            )
        ],
        rejected=["nightlife_events"],
        diagnostics={"sample_size": 0, "estimated_cost": 0.0},
        warnings=["Local AI disabled"],
    )

    encoded = vacation_blend_to_dict(blend)

    assert encoded == {
        "analysis_mode": "metadata_only",
        "confidence": "high",
        "primary": [
            {
                "theme_id": "road_trip",
                "label": "Road trip",
                "score": 82.5,
                "evidence": ["Travel across 8 cities"],
                "sample_event_ids": ["event-1", "event-2"],
            }
        ],
        "secondary": [
            {
                "theme_id": "food_drink",
                "label": "Food & drink",
                "score": 45.0,
                "evidence": ["Several restaurant stops"],
                "sample_event_ids": ["event-3"],
            }
        ],
        "rejected": ["nightlife_events"],
        "diagnostics": {"sample_size": 0, "estimated_cost": 0.0},
        "warnings": ["Local AI disabled"],
    }
    assert vacation_blend_from_dict(encoded) == blend


def test_task_one_does_not_expose_persistence_helpers():
    assert not hasattr(serialization, "vacation_blend_path")
    assert not hasattr(serialization, "save_vacation_blend")
    assert not hasattr(serialization, "load_vacation_blend")
