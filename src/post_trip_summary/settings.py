# src/post_trip_summary/settings.py
"""Global settings management via ~/.post-trip-summary/settings.toml."""
import os
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

SETTINGS_DIR = Path.home() / ".post-trip-summary"
SETTINGS_FILE = SETTINGS_DIR / "settings.toml"

DEFAULT_SETTINGS = {
    "vision": {
        "provider": "gemini",
        "gemini_api_key": "",
        "gemini_model": "gemini-2.5-flash",
        "claude_api_key": "",
        "claude_model": "claude-sonnet-4-20250514",
    },
    "geocoding": {
        "locationiq_api_key": "",
        "overpass_enabled": True,
        "overpass_radius_m": 300,
    },
}

_DEFAULT_TOML = """\
[vision]
# Vision provider: "gemini" or "claude"
provider = "gemini"

# Gemini settings (or set GOOGLE_API_KEY env var)
gemini_api_key = ""
gemini_model = "gemini-2.5-flash"

# Claude settings (or set ANTHROPIC_API_KEY env var)
claude_api_key = ""
claude_model = "claude-sonnet-4-20250514"

[geocoding]
# LocationIQ API key for faster geocoding (or set LOCATIONIQ_API_KEY env var)
# Free tier: 5,000 requests/day at 2 req/sec
# If not set, falls back to Nominatim (1 req/sec, no key needed)
locationiq_api_key = ""

# Overpass API for supplementary POI lookup
overpass_enabled = true
overpass_radius_m = 300
"""


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Merge overrides into defaults, preserving nested structure."""
    result = dict(defaults)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(settings_file: Path | None = None) -> dict:
    """Load settings from TOML file, merged with defaults."""
    path = settings_file or SETTINGS_FILE
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    text = path.read_text(encoding="utf-8")
    user_settings = tomllib.loads(text)
    return _deep_merge(DEFAULT_SETTINGS, user_settings)


def save_settings(settings: dict, settings_file: Path | None = None) -> None:
    """Write settings to TOML file."""
    path = settings_file or SETTINGS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for section, values in settings.items():
        if isinstance(values, dict):
            lines.append(f"[{section}]")
            for key, val in values.items():
                if isinstance(val, str):
                    lines.append(f'{key} = "{val}"')
                elif isinstance(val, bool):
                    lines.append(f"{key} = {'true' if val else 'false'}")
                else:
                    lines.append(f"{key} = {val}")
            lines.append("")
        else:
            if isinstance(values, str):
                lines.append(f'{section} = "{values}"')
            else:
                lines.append(f"{section} = {values}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_settings_file(settings_file: Path | None = None) -> Path:
    """Create settings file with commented defaults if it doesn't exist."""
    path = settings_file or SETTINGS_FILE
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_DEFAULT_TOML, encoding="utf-8")
    return path


def get_vision_settings(settings_file: Path | None = None) -> dict:
    """Return a flat dict with provider, api_key, and model for the active provider."""
    settings = load_settings(settings_file)
    vision = settings["vision"]
    provider = vision["provider"]

    if provider == "gemini":
        api_key = vision.get("gemini_api_key", "") or os.environ.get("GOOGLE_API_KEY", "")
        model = vision.get("gemini_model", "gemini-2.0-flash")
    elif provider == "claude":
        api_key = vision.get("claude_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        model = vision.get("claude_model", "claude-sonnet-4-20250514")
    else:
        raise ValueError(f"Unknown vision provider: {provider}. Options: gemini, claude")

    return {
        "provider": provider,
        "api_key": api_key or None,
        "model": model,
    }


def get_geocoding_settings(settings_file: Path | None = None) -> dict:
    """Return geocoding settings with env var fallback for API key."""
    settings = load_settings(settings_file)
    geo = settings["geocoding"]
    api_key = geo.get("locationiq_api_key", "") or os.environ.get("LOCATIONIQ_API_KEY", "")
    return {
        "locationiq_api_key": api_key or None,
        "overpass_enabled": geo.get("overpass_enabled", True),
        "overpass_radius_m": geo.get("overpass_radius_m", 75),
    }
