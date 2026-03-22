# src/post_trip_summary/vision/client.py
"""AI vision API abstraction layer with pluggable providers."""
import base64
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VisionResult:
    description: str
    landmark: str | None = None
    text_found: str | None = None
    confidence: str = "medium"


class VisionProvider(ABC):
    @abstractmethod
    def analyze(self, image_data: bytes, media_type: str = "image/jpeg", purpose: str = "landmark", context: str = "") -> VisionResult:
        ...

    @abstractmethod
    def estimate_cost(self, num_images: int, avg_tokens_per_image: int = 1600) -> float:
        ...

    def synthesize(self, prompt: str) -> str:
        """Text-only call to synthesize multiple descriptions into one."""
        raise NotImplementedError("Provider does not support synthesis")


# Approximate Claude pricing (input tokens for images)
_INPUT_COST_PER_MTOK = 3.0   # $/M input tokens (Claude Sonnet)
_OUTPUT_COST_PER_MTOK = 15.0  # $/M output tokens


class ClaudeProvider(VisionProvider):
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def analyze(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "landmark",
        context: str = "",
    ) -> VisionResult:
        """Send an image to Claude Vision and parse the result."""
        from post_trip_summary.vision.prompts import get_prompt

        b64_image = base64.b64encode(image_data).decode("utf-8")
        prompt = get_prompt(purpose, context=context)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64_image},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        text = response.content[0].text
        try:
            data = json.loads(text)
            return VisionResult(
                description=data.get("description", ""),
                landmark=data.get("landmark"),
                text_found=data.get("text_found"),
                confidence=data.get("confidence", "medium"),
            )
        except json.JSONDecodeError:
            return VisionResult(description=text)

    def estimate_cost(self, num_images: int, avg_tokens_per_image: int = 1600) -> float:
        """Estimate API cost for a batch of images."""
        input_tokens = num_images * avg_tokens_per_image
        output_tokens = num_images * 200
        input_cost = (input_tokens / 1_000_000) * _INPUT_COST_PER_MTOK
        output_cost = (output_tokens / 1_000_000) * _OUTPUT_COST_PER_MTOK
        return round(input_cost + output_cost, 4)

    def synthesize(self, prompt: str) -> str:
        """Text-only call to synthesize descriptions."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        try:
            data = json.loads(text)
            return data.get("description", text)
        except json.JSONDecodeError:
            return text


# Backward-compatible alias
VisionClient = ClaudeProvider


def create_provider(name: str = "gemini", api_key: str | None = None, model: str | None = None) -> VisionProvider:
    """Factory -- returns the appropriate provider instance."""
    if name == "claude":
        return ClaudeProvider(api_key=api_key, model=model or "claude-sonnet-4-20250514")
    elif name == "gemini":
        from post_trip_summary.vision.gemini import GeminiProvider
        return GeminiProvider(api_key=api_key, model=model or "gemini-2.5-flash")
    else:
        raise ValueError(f"Unknown vision provider: {name}. Options: claude, gemini")
