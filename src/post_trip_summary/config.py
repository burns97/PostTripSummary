# src/post_trip_summary/config.py
"""Session configuration and management."""
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BASE_DIR = Path.home() / ".post-trip-summary" / "sessions"

DEFAULT_SETTINGS = {
    "cluster_time_gap_minutes": 15,
    "cluster_distance_meters": 200,
    "quality_cull_percentile": 15,
}

STAGES = ["new", "setup", "ingested", "reviewed", "enriched", "highlights_done", "generated"]


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")


@dataclass
class SessionConfig:
    name: str
    slug: str
    session_dir: Path
    current_stage: str = "new"
    inputs: dict = field(default_factory=dict)
    settings: dict = field(default_factory=lambda: dict(DEFAULT_SETTINGS))

    def save(self) -> None:
        self.session_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "name": self.name,
            "slug": self.slug,
            "current_stage": self.current_stage,
            "inputs": self.inputs,
            "settings": self.settings,
        }
        config_path = self.session_dir / "config.json"
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def stage_file(self, stage: str) -> Path:
        filenames = {
            # New wizard stages
            "ingested": "trip_ingested.json",
            "reviewed": "trip_reviewed.json",
            "enriched": "trip_enriched.json",
            "highlights_done": "trip_final.json",
            # Legacy (deprecated — kept so existing CLI commands don't crash)
            "ingest": "trip_data.json",
            "skeleton": "trip_skeleton.json",
            "skeleton_reviewed": "trip_skeleton_reviewed.json",
            "final": "trip_final.json",
        }
        if stage not in filenames:
            raise ValueError(f"No file for stage: {stage}")
        return self.session_dir / filenames[stage]

    @property
    def output_dir(self) -> Path:
        return self.session_dir / "output"


def create_session(name: str, base_dir: Path | None = None) -> SessionConfig:
    base = base_dir or DEFAULT_BASE_DIR
    slug = _slugify(name)
    session_dir = base / slug
    session = SessionConfig(name=name, slug=slug, session_dir=session_dir)
    session.save()
    return session


def load_session(slug: str, base_dir: Path | None = None) -> SessionConfig:
    base = base_dir or DEFAULT_BASE_DIR
    config_path = base / slug / "config.json"
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return SessionConfig(
        name=data["name"],
        slug=data["slug"],
        session_dir=base / slug,
        current_stage=data.get("current_stage", "new"),
        inputs=data.get("inputs", {}),
        settings={**DEFAULT_SETTINGS, **data.get("settings", {})},
    )


def list_sessions(base_dir: Path | None = None) -> list[SessionConfig]:
    base = base_dir or DEFAULT_BASE_DIR
    if not base.exists():
        return []
    sessions = []
    for child in sorted(base.iterdir()):
        config_path = child / "config.json"
        if config_path.exists():
            sessions.append(load_session(child.name, base_dir=base))
    return sessions


def delete_session(slug: str, base_dir: Path | None = None) -> None:
    base = base_dir or DEFAULT_BASE_DIR
    session_dir = base / slug
    if session_dir.exists():
        shutil.rmtree(session_dir)
