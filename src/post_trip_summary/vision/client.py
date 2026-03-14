# src/post_trip_summary/vision/client.py
"""AI vision API abstraction layer (Claude Vision)."""
import base64
import json
from dataclasses import dataclass

import anthropic


@dataclass
class VisionResult:
    description: str
    landmark: str | None = None
    text_found: str | None = None
    confidence: str = "medium"


# Approximate Claude pricing (input tokens for images)
# Claude vision: ~1600 tokens per image + output tokens
_INPUT_COST_PER_MTOK = 3.0   # $/M input tokens (Claude Sonnet)
_OUTPUT_COST_PER_MTOK = 15.0  # $/M output tokens


class VisionClient:
    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def analyze(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "landmark",
    ) -> VisionResult:
        """Send an image to Claude Vision and parse the result."""
        from post_trip_summary.vision.prompts import get_prompt

        b64_image = base64.b64encode(image_data).decode("utf-8")
        prompt = get_prompt(purpose)

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
        output_tokens = num_images * 200  # ~200 output tokens per response
        input_cost = (input_tokens / 1_000_000) * _INPUT_COST_PER_MTOK
        output_cost = (output_tokens / 1_000_000) * _OUTPUT_COST_PER_MTOK
        return round(input_cost + output_cost, 4)
