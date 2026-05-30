import base64
import json

import pytest

from post_trip_summary.vision.client import VisionResult


class FakeTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def __call__(self, url, payload, timeout):
        self.calls.append((url, payload, timeout))
        if self.error:
            raise self.error
        return self.response


def test_ollama_analyze_posts_image_and_parses_json_result():
    from post_trip_summary.vision.ollama import OllamaProvider

    response = {
        "response": json.dumps({
            "description": "A harbor at sunset.",
            "landmark": "Sydney Opera House",
            "text_found": None,
            "confidence": "high",
        })
    }
    transport = FakeTransport(response=response)
    provider = OllamaProvider(
        model="gemma4:e2b",
        base_url="http://localhost:11434",
        timeout_seconds=45,
        transport=transport,
    )

    result = provider.analyze(b"fake-image", media_type="image/jpeg", purpose="landmark", context="Location: Sydney")

    assert isinstance(result, VisionResult)
    assert result.description == "A harbor at sunset."
    assert result.landmark == "Sydney Opera House"
    assert result.confidence == "high"
    url, payload, timeout = transport.calls[0]
    assert url == "http://localhost:11434/api/generate"
    assert timeout == 45
    assert payload["model"] == "gemma4:e2b"
    assert payload["stream"] is False
    assert payload["format"] == "json"
    assert payload["images"] == [base64.b64encode(b"fake-image").decode("ascii")]


def test_ollama_analyze_uses_plain_text_when_model_does_not_return_json():
    from post_trip_summary.vision.ollama import OllamaProvider

    transport = FakeTransport(response={"response": "A mountain lake with people walking nearby."})
    provider = OllamaProvider(transport=transport)

    result = provider.analyze(b"fake-image", purpose="scene")

    assert result == VisionResult(description="A mountain lake with people walking nearby.")


def test_ollama_analyze_montage_returns_parsed_dict():
    from post_trip_summary.vision.ollama import OllamaProvider

    response = {"response": '{"summary": "A market visit.", "highlights": [1, 3]}'}
    transport = FakeTransport(response=response)
    provider = OllamaProvider(transport=transport)

    result = provider.analyze_montage(b"montage", purpose="montage", image_count=4)

    assert result == {"summary": "A market visit.", "highlights": [1, 3]}


def test_ollama_batch_describe_supports_prompt_kwargs():
    from post_trip_summary.vision.ollama import OllamaProvider

    response = {
        "response": json.dumps({
            "photos": {
                "1": {"description": "Lunch table.", "landmark": None, "text_found": None}
            }
        })
    }
    transport = FakeTransport(response=response)
    provider = OllamaProvider(transport=transport)

    result = provider.analyze_montage(
        b"montage",
        purpose="batch_describe",
        image_count=1,
        event_count=1,
        event_groups='Event "Lunch" (photos 1):\nLocation: Paris',
    )

    assert result["photos"]["1"]["description"] == "Lunch table."


def test_ollama_synthesize_returns_description_field_when_present():
    from post_trip_summary.vision.ollama import OllamaProvider

    transport = FakeTransport(response={"response": '{"description": "A unified trip paragraph."}'})
    provider = OllamaProvider(transport=transport)

    result = provider.synthesize("Write a paragraph")

    assert result == "A unified trip paragraph."
    _, payload, _ = transport.calls[0]
    assert "images" not in payload


def test_ollama_synthesize_returns_raw_json_for_non_description_payload():
    from post_trip_summary.vision.ollama import OllamaProvider

    raw = '{"narrative": "A journal-style paragraph."}'
    transport = FakeTransport(response={"response": raw})
    provider = OllamaProvider(transport=transport)

    result = provider.synthesize("Write a narrative")

    assert result == raw


def test_ollama_estimate_cost_is_zero():
    from post_trip_summary.vision.ollama import OllamaProvider

    provider = OllamaProvider()

    assert provider.estimate_cost(500) == 0.0


def test_ollama_transport_errors_are_wrapped():
    from post_trip_summary.vision.ollama import OllamaProvider, OllamaProviderError

    provider = OllamaProvider(transport=FakeTransport(error=OSError("connection refused")))

    with pytest.raises(OllamaProviderError, match="Could not reach Ollama"):
        provider.analyze(b"fake-image")
