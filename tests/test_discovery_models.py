from dataclasses import fields

import pytest

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.serialization import (
    load_vacation_blend,
    save_vacation_blend,
    vacation_blend_from_dict,
    vacation_blend_path,
    vacation_blend_to_dict,
)
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


def test_vacation_blend_to_dict_deep_copies_nested_diagnostics():
    blend = VacationBlend(
        analysis_mode="metadata_only",
        confidence="medium",
        primary=[],
        secondary=[],
        rejected=[],
        diagnostics={
            "counts": {
                "events_by_theme": {"road_trip": 3},
                "sample_event_ids": ["event-1", "event-2"],
            }
        },
        warnings=[],
    )

    encoded = vacation_blend_to_dict(blend)
    encoded["diagnostics"]["counts"]["events_by_theme"]["road_trip"] = 99
    encoded["diagnostics"]["counts"]["sample_event_ids"].append("event-3")

    assert blend.diagnostics == {
        "counts": {
            "events_by_theme": {"road_trip": 3},
            "sample_event_ids": ["event-1", "event-2"],
        }
    }


def test_vacation_blend_from_dict_deep_copies_nested_diagnostics():
    data = {
        "analysis_mode": "metadata_only",
        "confidence": "medium",
        "primary": [],
        "secondary": [],
        "rejected": [],
        "diagnostics": {
            "counts": {
                "events_by_theme": {"road_trip": 3},
                "sample_event_ids": ["event-1", "event-2"],
            }
        },
        "warnings": [],
    }

    blend = vacation_blend_from_dict(data)
    blend.diagnostics["counts"]["events_by_theme"]["road_trip"] = 99
    blend.diagnostics["counts"]["sample_event_ids"].append("event-3")

    assert data["diagnostics"] == {
        "counts": {
            "events_by_theme": {"road_trip": 3},
            "sample_event_ids": ["event-1", "event-2"],
        }
    }


def test_vacation_blend_persistence_helpers_round_trip(tmp_path):
    blend = VacationBlend(
        analysis_mode="metadata_only",
        confidence="medium",
        primary=[
            ThemeScore(
                theme_id="culture_sightseeing",
                label="Culture & sightseeing",
                score=55.0,
                evidence=["Museum visit"],
                sample_event_ids=["event-1"],
            )
        ],
        secondary=[],
        rejected=[],
        diagnostics={"sample_size": 1},
        warnings=[],
    )
    path = vacation_blend_path(tmp_path / "session")

    save_vacation_blend(path, blend)

    assert path == tmp_path / "session" / "vacation_blend.json"
    assert load_vacation_blend(path) == blend
