"""Serialization helpers for Vacation Blend artifacts."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.taxonomy import validate_theme_ids


def vacation_blend_path(session_dir: Path) -> Path:
    return session_dir / "vacation_blend.json"


def encode_vacation_blend(blend: VacationBlend) -> dict:
    validate_theme_ids(blend.primary_themes)
    validate_theme_ids(blend.secondary_themes)
    validate_theme_ids(blend.rejected_themes)
    validate_theme_ids([score.theme_id for score in blend.theme_scores])
    return asdict(blend)


def decode_vacation_blend(data: dict) -> VacationBlend:
    theme_scores = [
        ThemeScore(
            theme_id=item["theme_id"],
            score=item["score"],
            confidence=item["confidence"],
            evidence=list(item.get("evidence", [])),
            sources=list(item.get("sources", [])),
        )
        for item in data.get("theme_scores", [])
    ]
    blend = VacationBlend(
        primary_themes=list(data.get("primary_themes", [])),
        secondary_themes=list(data.get("secondary_themes", [])),
        rejected_themes=list(data.get("rejected_themes", [])),
        confidence=data.get("confidence", "low"),
        evidence=list(data.get("evidence", [])),
        theme_scores=theme_scores,
        analysis_mode=data.get("analysis_mode", "metadata_only"),
        sample_size=int(data.get("sample_size", 0)),
        local_model=data.get("local_model"),
        cloud_model=data.get("cloud_model"),
        estimated_cost=float(data.get("estimated_cost", 0.0)),
        warnings=list(data.get("warnings", [])),
    )
    encode_vacation_blend(blend)
    return blend


def save_vacation_blend(path: Path, blend: VacationBlend) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(encode_vacation_blend(blend), indent=2),
        encoding="utf-8",
    )


def load_vacation_blend(path: Path) -> VacationBlend:
    return decode_vacation_blend(json.loads(path.read_text(encoding="utf-8")))
