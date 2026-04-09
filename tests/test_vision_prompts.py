# tests/test_vision_prompts.py
from post_trip_summary.vision.prompts import get_prompt, PURPOSES


def test_all_purposes_have_prompts():
    for purpose in PURPOSES:
        kwargs = {}
        if purpose == "synthesize":
            kwargs = {"image_count": 3, "descriptions": "1. A photo\n2. Another\n3. Third"}
        elif purpose == "montage":
            kwargs = {"image_count": 5}
        elif purpose == "narrative":
            kwargs = {"montage_summary": "Event summary", "descriptions": "1. Detail\n2. More"}
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


def test_montage_prompt_requests_json():
    prompt = get_prompt("montage", context="Location: Hobbiton", image_count=15)
    assert "JSON" in prompt or "json" in prompt
    assert "summary" in prompt
    assert "highlights" in prompt
    assert "15" in prompt


def test_narrative_prompt_requests_json():
    prompt = get_prompt("narrative", context="Location: Hobbiton",
                        montage_summary="We toured Hobbiton.",
                        descriptions="1. A hobbit hole\n2. The Green Dragon")
    assert "JSON" in prompt or "json" in prompt
    assert "narrative" in prompt
    assert "We toured Hobbiton" in prompt
