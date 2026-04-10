# tests/test_settings.py
import os
from pathlib import Path
from unittest.mock import patch

from post_trip_summary.settings import (
    load_settings, save_settings, get_vision_settings, ensure_settings_file,
    DEFAULT_SETTINGS,
)


def test_load_defaults_no_file(tmp_path):
    """Returns defaults when no settings.toml exists."""
    settings = load_settings(tmp_path / "nonexistent.toml")
    assert settings == DEFAULT_SETTINGS
    assert settings["vision"]["provider"] == "gemini"


def test_save_and_load_round_trip(tmp_path):
    """Write then read back settings."""
    path = tmp_path / "settings.toml"
    settings = {
        "vision": {
            "provider": "claude",
            "gemini_api_key": "",
            "gemini_model": "gemini-2.5-flash",
            "claude_api_key": "sk-test-123",
            "claude_model": "claude-sonnet-4-20250514",
        },
    }
    save_settings(settings, path)
    loaded = load_settings(path)
    assert loaded["vision"]["provider"] == "claude"
    assert loaded["vision"]["claude_api_key"] == "sk-test-123"


def test_env_var_fallback_gemini(tmp_path):
    """Env var used when settings key is empty."""
    path = tmp_path / "settings.toml"
    save_settings(DEFAULT_SETTINGS, path)
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "env-gemini-key"}):
        vs = get_vision_settings(path)
        assert vs["api_key"] == "env-gemini-key"
        assert vs["provider"] == "gemini"


def test_env_var_fallback_claude(tmp_path):
    """Env var used for claude when settings key is empty."""
    path = tmp_path / "settings.toml"
    settings = dict(DEFAULT_SETTINGS)
    settings["vision"] = dict(settings["vision"])
    settings["vision"]["provider"] = "claude"
    save_settings(settings, path)
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-claude-key"}):
        vs = get_vision_settings(path)
        assert vs["api_key"] == "env-claude-key"
        assert vs["provider"] == "claude"


def test_settings_file_value_takes_precedence(tmp_path):
    """Settings file value used over env var."""
    path = tmp_path / "settings.toml"
    settings = dict(DEFAULT_SETTINGS)
    settings["vision"] = dict(settings["vision"])
    settings["vision"]["gemini_api_key"] = "file-key"
    save_settings(settings, path)
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "env-key"}):
        vs = get_vision_settings(path)
        assert vs["api_key"] == "file-key"


def test_get_vision_settings(tmp_path):
    """Returns flat dict with provider, api_key, model."""
    path = tmp_path / "settings.toml"
    save_settings(DEFAULT_SETTINGS, path)
    vs = get_vision_settings(path)
    assert set(vs.keys()) == {"provider", "api_key", "model", "billing"}
    assert vs["provider"] == "gemini"
    assert vs["model"] == "gemini-2.5-flash"


def test_ensure_settings_file_creates(tmp_path):
    """Creates settings file with defaults if missing."""
    path = tmp_path / "subdir" / "settings.toml"
    result = ensure_settings_file(path)
    assert result == path
    assert path.exists()
    loaded = load_settings(path)
    assert loaded["vision"]["provider"] == "gemini"
