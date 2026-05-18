"""Dataclasses for Vacation Blend Discovery."""
from __future__ import annotations

from dataclasses import dataclass, field

CONFIDENCE_LEVELS = {"low", "medium", "high"}


@dataclass(frozen=True)
class ThemeDefinition:
    id: str
    label: str
    description: str


@dataclass
class ThemeScore:
    theme_id: str
    score: float
    confidence: str
    evidence: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {self.confidence}")
        self.score = max(0.0, min(100.0, float(self.score)))


@dataclass
class VacationBlend:
    primary_themes: list[str]
    secondary_themes: list[str]
    rejected_themes: list[str]
    confidence: str
    evidence: list[str]
    theme_scores: list[ThemeScore]
    analysis_mode: str
    sample_size: int = 0
    local_model: str | None = None
    cloud_model: str | None = None
    estimated_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"invalid confidence: {self.confidence}")
