# tests/test_vision_client.py
from unittest.mock import patch, MagicMock
from post_trip_summary.vision.client import (
    ClaudeProvider, VisionClient, VisionResult, VisionProvider, create_provider,
)


def test_vision_result_creation():
    result = VisionResult(description="Eiffel Tower from Trocadero", landmark="Eiffel Tower", text_found=None, confidence="high")
    assert result.landmark == "Eiffel Tower"
    assert result.text_found is None


def test_claude_provider_analyze_mock():
    """Test that analyze calls the API with correct structure."""
    mock_anthropic = MagicMock()
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"description": "Eiffel Tower", "landmark": "Eiffel Tower", "text_found": null}')]
    mock_client.messages.create.return_value = mock_response

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        provider = ClaudeProvider(api_key="test-key")
        jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 100 + b'\xff\xd9'
        result = provider.analyze(image_data=jpeg_bytes, media_type="image/jpeg", purpose="landmark")
        assert mock_client.messages.create.called


def test_claude_estimate_cost():
    provider = ClaudeProvider.__new__(ClaudeProvider)
    cost = provider.estimate_cost(num_images=100, avg_tokens_per_image=1500)
    assert cost > 0
    assert isinstance(cost, float)


def test_backward_compat_alias():
    """VisionClient is an alias for ClaudeProvider."""
    assert VisionClient is ClaudeProvider


def test_create_provider_claude():
    """Factory returns ClaudeProvider for 'claude'."""
    mock_anthropic = MagicMock()
    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        provider = create_provider("claude", api_key="test")
    assert isinstance(provider, ClaudeProvider)
    assert isinstance(provider, VisionProvider)


def test_create_provider_gemini():
    """Factory returns GeminiProvider for 'gemini'."""
    mock_google = MagicMock()
    mock_genai = MagicMock()
    with patch.dict("sys.modules", {"google": mock_google, "google.genai": mock_genai}):
        # Need to clear cached module to force reimport
        import sys
        sys.modules.pop("post_trip_summary.vision.gemini", None)
        provider = create_provider("gemini", api_key="test")
        from post_trip_summary.vision.gemini import GeminiProvider
        assert isinstance(provider, GeminiProvider)
        assert isinstance(provider, VisionProvider)


def test_create_provider_unknown():
    """Factory raises ValueError for unknown provider."""
    try:
        create_provider("openai")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown vision provider" in str(e)


def test_gemini_analyze_montage_mock(monkeypatch):
    """Test Gemini provider's analyze_montage with mocked API."""
    from unittest.mock import MagicMock
    from post_trip_summary.vision.gemini import GeminiProvider

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"summary": "Visited a movie set.", "highlights": [1, 3, 5]}'
    mock_client.models.generate_content.return_value = mock_response

    provider = GeminiProvider.__new__(GeminiProvider)
    provider._client = mock_client
    provider._model = "gemini-2.5-flash"

    result = provider.analyze_montage(
        image_data=b"fake-jpeg",
        media_type="image/jpeg",
        purpose="montage",
        context="Location: Hobbiton",
        image_count=10,
    )
    assert result["summary"] == "Visited a movie set."
    assert result["highlights"] == [1, 3, 5]
