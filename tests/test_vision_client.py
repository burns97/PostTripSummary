# tests/test_vision_client.py
from pathlib import Path
from unittest.mock import patch, MagicMock
from post_trip_summary.vision.client import VisionClient, VisionResult


def test_vision_result_creation():
    result = VisionResult(description="Eiffel Tower from Trocadero", landmark="Eiffel Tower", text_found=None, confidence="high")
    assert result.landmark == "Eiffel Tower"
    assert result.text_found is None


def test_vision_client_analyze_mock():
    """Test that analyze calls the API with correct structure."""
    with patch("post_trip_summary.vision.client.anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"description": "Eiffel Tower", "landmark": "Eiffel Tower", "text_found": null}')]
        mock_client.messages.create.return_value = mock_response

        client = VisionClient(api_key="test-key")
        # Create a tiny valid JPEG for testing
        import struct
        jpeg_bytes = b'\xff\xd8\xff\xe0' + b'\x00' * 100 + b'\xff\xd9'
        result = client.analyze(image_data=jpeg_bytes, media_type="image/jpeg", purpose="landmark")
        assert mock_client.messages.create.called


def test_estimate_cost():
    client = VisionClient.__new__(VisionClient)
    cost = client.estimate_cost(num_images=100, avg_tokens_per_image=1500)
    assert cost > 0
    assert isinstance(cost, float)
