"""Serialization helpers for Vacation Blend artifacts."""
from __future__ import annotations

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.taxonomy import validate_theme_ids


def _theme_score_to_dict(score: ThemeScore) -> dict:
    return {
        "theme_id": score.theme_id,
        "label": score.label,
        "score": score.score,
        "evidence": list(score.evidence),
        "sample_event_ids": list(score.sample_event_ids),
    }


def _theme_score_from_dict(data: dict) -> ThemeScore:
    return ThemeScore(
        theme_id=data["theme_id"],
        label=data["label"],
        score=float(data["score"]),
        evidence=list(data.get("evidence", [])),
        sample_event_ids=list(data.get("sample_event_ids", [])),
    )


def vacation_blend_to_dict(blend: VacationBlend) -> dict:
    validate_theme_ids([score.theme_id for score in blend.primary])
    validate_theme_ids([score.theme_id for score in blend.secondary])
    validate_theme_ids(blend.rejected)
    return {
        "analysis_mode": blend.analysis_mode,
        "confidence": blend.confidence,
        "primary": [_theme_score_to_dict(score) for score in blend.primary],
        "secondary": [_theme_score_to_dict(score) for score in blend.secondary],
        "rejected": list(blend.rejected),
        "diagnostics": dict(blend.diagnostics),
        "warnings": list(blend.warnings),
    }


def vacation_blend_from_dict(data: dict) -> VacationBlend:
    blend = VacationBlend(
        analysis_mode=data["analysis_mode"],
        confidence=data["confidence"],
        primary=[_theme_score_from_dict(item) for item in data.get("primary", [])],
        secondary=[_theme_score_from_dict(item) for item in data.get("secondary", [])],
        rejected=list(data.get("rejected", [])),
        diagnostics=dict(data.get("diagnostics", {})),
        warnings=list(data.get("warnings", [])),
    )
    vacation_blend_to_dict(blend)
    return blend
