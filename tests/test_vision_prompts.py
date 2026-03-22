# tests/test_vision_prompts.py
from post_trip_summary.vision.prompts import get_prompt, PURPOSES


def test_all_purposes_have_prompts():
    for purpose in PURPOSES:
        kwargs = {}
        if purpose == "synthesize":
            kwargs = {"image_count": 3, "descriptions": "1. A photo\n2. Another\n3. Third"}
        prompt = get_prompt(purpose, **kwargs)
        assert isinstance(prompt, str)
        assert len(prompt) > 50


def test_landmark_prompt_requests_json():
    prompt = get_prompt("landmark")
    assert "JSON" in prompt or "json" in prompt


def test_sign_prompt_requests_text():
    prompt = get_prompt("sign")
    assert "text" in prompt.lower()


def test_unknown_purpose_raises():
    import pytest
    with pytest.raises(ValueError):
        get_prompt("nonexistent")
