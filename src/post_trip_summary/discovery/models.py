"""Dataclasses for Vacation Blend Discovery."""
from __future__ import annotations

from dataclasses import dataclass

CONFIDENCE_LEVELS = {"low", "medium", "high"}


@dataclass(frozen=True)
class ThemeDefinition:
    id: str
    label: str
    description: str


@dataclass
class ThemeScore:
    theme_id: str
    label: str
    score: float
    evidence: list[str]
    sample_event_ids: list[str]


@dataclass
class VacationBlend:
    analysis_mode: str
    confidence: str
    primary: list[ThemeScore]
    secondary: list[ThemeScore]
    rejected: list[str]
    diagnostics: dict[str, object]
    warnings: list[str]

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {self.confidence}")
