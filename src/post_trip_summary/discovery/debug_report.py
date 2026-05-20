"""Markdown debug report generation for Vacation Blend discovery."""
from __future__ import annotations

from pathlib import Path

from post_trip_summary.discovery.models import ThemeScore, VacationBlend
from post_trip_summary.discovery.taxonomy import get_theme_label


def vacation_blend_debug_report_path(session_dir: Path) -> Path:
    """Return the standard path for the Vacation Blend debug report."""
    return session_dir / "vacation_blend_debug.md"


def build_vacation_blend_debug_report(blend: VacationBlend) -> str:
    """Build a human-readable debug report for Vacation Blend scoring."""
    lines: list[str] = [
        "# Vacation Blend Debug Report",
        "",
        "## Summary",
        f"- Analysis mode: {blend.analysis_mode}",
        f"- Confidence: {blend.confidence}",
        f"- Primary themes: {_format_theme_list(blend.primary)}",
        f"- Secondary themes: {_format_theme_list(blend.secondary)}",
        f"- Rejected themes: {_format_rejected(blend.rejected)}",
        "",
        "## Diagnostics",
    ]

    diagnostics = _diagnostics_without_theme_scores(blend.diagnostics)
    for key, value in _flatten_diagnostics(diagnostics):
        lines.append(f"- {key}: {_format_value(value)}")
    if not diagnostics:
        lines.append("- None")

    lines.extend(["", "## Theme Scores"])
    for theme_id, score in _ranked_theme_scores(blend):
        lines.append(
            f"- {get_theme_label(theme_id)} ({theme_id}): "
            f"{_format_score(score)} - {_theme_status(theme_id, blend)}"
        )

    lines.extend(["", "## Primary Theme Evidence"])
    _append_theme_evidence(lines, blend.primary)

    lines.extend(["", "## Secondary Theme Evidence"])
    _append_theme_evidence(lines, blend.secondary)

    lines.extend(["", "## Warnings"])
    if blend.warnings:
        for warning in blend.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- None")

    return "\n".join(lines) + "\n"


def save_vacation_blend_debug_report(path: Path, blend: VacationBlend) -> None:
    """Persist a Vacation Blend debug report to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_vacation_blend_debug_report(blend), encoding="utf-8")


def _format_theme_list(scores: list[ThemeScore]) -> str:
    if not scores:
        return "none"
    return ", ".join(
        f"{score.label or get_theme_label(score.theme_id)} ({_format_score(score.score)})"
        for score in scores
    )


def _format_rejected(theme_ids: list[str]) -> str:
    if not theme_ids:
        return "none"
    return ", ".join(f"{get_theme_label(theme_id)} ({theme_id})" for theme_id in theme_ids)


def _diagnostics_without_theme_scores(diagnostics: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in diagnostics.items()
        if key != "theme_scores"
    }


def _flatten_diagnostics(
    diagnostics: dict[str, object],
    prefix: str = "",
) -> list[tuple[str, object]]:
    flattened: list[tuple[str, object]] = []
    for key in sorted(diagnostics):
        value = diagnostics[key]
        dotted_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.extend(_flatten_diagnostics(value, dotted_key))
        else:
            flattened.append((dotted_key, value))
    return flattened


def _ranked_theme_scores(blend: VacationBlend) -> list[tuple[str, float]]:
    diagnostics_scores = blend.diagnostics.get("theme_scores", {})
    scores: dict[str, float] = {}
    if isinstance(diagnostics_scores, dict):
        for theme_id, score in diagnostics_scores.items():
            scores[str(theme_id)] = _coerce_score(score)

    for score in [*blend.primary, *blend.secondary]:
        scores[score.theme_id] = _coerce_score(score.score)
    for theme_id in blend.rejected:
        scores.setdefault(theme_id, 0.0)

    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def _theme_status(theme_id: str, blend: VacationBlend) -> str:
    if theme_id in {score.theme_id for score in blend.primary}:
        return "primary"
    if theme_id in {score.theme_id for score in blend.secondary}:
        return "secondary"
    if theme_id in set(blend.rejected):
        return "rejected"
    return "not selected"


def _append_theme_evidence(lines: list[str], scores: list[ThemeScore]) -> None:
    if not scores:
        lines.append("- None")
        return

    for score in scores:
        lines.append(
            f"### {score.label or get_theme_label(score.theme_id)} "
            f"({score.theme_id}, {_format_score(score.score)})"
        )
        if score.evidence:
            lines.append("- Evidence:")
            for item in score.evidence:
                lines.append(f"  - {item}")
        else:
            lines.append("- Evidence: none")
        if score.sample_event_ids:
            lines.append(f"- Sample events: {', '.join(score.sample_event_ids)}")
        else:
            lines.append("- Sample events: none")


def _coerce_score(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_score(score: object) -> str:
    return f"{_coerce_score(score):.1f}"


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)
