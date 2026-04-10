# tests/test_gemini_provider.py
import json
from unittest.mock import patch, MagicMock

from post_trip_summary.vision.client import VisionResult


def test_gemini_analyze_mock():
    """Mock google.genai, verify generate_content called, JSON parsed to VisionResult."""
    mock_genai = MagicMock()
    mock_types = MagicMock()
    mock_client_instance = MagicMock()
    mock_genai.Client.return_value = mock_client_instance

    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "description": "The Colosseum in Rome",
        "landmark": "Colosseum",
        "text_found": None,
        "confidence": "high",
    })
    mock_client_instance.models.generate_content.return_value = mock_response

    with patch.dict("sys.modules", {"google": MagicMock(), "google.genai": mock_genai, "google.genai.types": mock_types}):
        from post_trip_summary.vision.gemini import GeminiProvider
        # Patch the import inside __init__
        with patch("post_trip_summary.vision.gemini.GeminiProvider.__init__", lambda self, **kwargs: None):
            provider = GeminiProvider.__new__(GeminiProvider)
            provider._client = mock_client_instance
            provider._model = "gemini-2.0-flash"

        jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 100 + b'\xff\xd9'

        # Need to patch the imports inside analyze
        with patch("google.genai.types", mock_types):
            result = provider.analyze(image_data=jpeg_bytes, media_type="image/jpeg", purpose="landmark")

    assert isinstance(result, VisionResult)
    assert result.landmark == "Colosseum"
    assert result.description == "The Colosseum in Rome"
    assert result.confidence == "high"
    assert mock_client_instance.models.generate_content.called


def test_gemini_estimate_cost_free():
    """Gemini Flash free tier returns 0.0."""
    with patch.dict("sys.modules", {"google": MagicMock(), "google.genai": MagicMock()}):
        from post_trip_summary.vision.gemini import GeminiProvider
        provider = GeminiProvider.__new__(GeminiProvider)
        provider._billing = False
        assert provider.estimate_cost(100) == 0.0
        assert provider.estimate_cost(0) == 0.0


def test_gemini_estimate_cost_paid():
    """Gemini Flash paid tier returns non-zero cost."""
    with patch.dict("sys.modules", {"google": MagicMock(), "google.genai": MagicMock()}):
        from post_trip_summary.vision.gemini import GeminiProvider
        provider = GeminiProvider.__new__(GeminiProvider)
        provider._billing = True
        cost = provider.estimate_cost(100)
        assert cost > 0.0
