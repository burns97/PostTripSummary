"""Serialization helpers for Vacation Blend artifacts."""
from __future__ import annotations

import json
from pathlib import Path

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.taxonomy import validate_theme_ids


def _copy_plain_data(value: object) -> object:
    if isinstance(value, dict):
        return {key: _copy_plain_data(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_plain_data(item) for item in value]
    return value


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
        "diagnostics": _copy_plain_data(blend.diagnostics),
        "warnings": list(blend.warnings),
    }


def vacation_blend_from_dict(data: dict) -> VacationBlend:
    diagnostics = _copy_plain_data(data.get("diagnostics", {}))
    if not isinstance(diagnostics, dict):
        raise ValueError("diagnostics must be a dict")

    blend = VacationBlend(
        analysis_mode=data["analysis_mode"],
        confidence=data["confidence"],
        primary=[_theme_score_from_dict(item) for item in data.get("primary", [])],
        secondary=[_theme_score_from_dict(item) for item in data.get("secondary", [])],
        rejected=list(data.get("rejected", [])),
        diagnostics=diagnostics,
        warnings=list(data.get("warnings", [])),
    )
    vacation_blend_to_dict(blend)
    return blend


def vacation_blend_path(session_dir: Path) -> Path:
    return session_dir / "vacation_blend.json"


def save_vacation_blend(path: Path, blend: VacationBlend) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(vacation_blend_to_dict(blend), indent=2),
        encoding="utf-8",
    )


def load_vacation_blend(path: Path) -> VacationBlend:
    return vacation_blend_from_dict(json.loads(path.read_text(encoding="utf-8")))
