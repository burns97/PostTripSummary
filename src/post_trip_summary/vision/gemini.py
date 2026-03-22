# src/post_trip_summary/vision/gemini.py
"""Google Gemini vision provider."""
import json
import time

from post_trip_summary.vision.client import VisionProvider, VisionResult


class QuotaExhaustedError(Exception):
    """Raised when the API quota is fully exhausted (limit: 0), not just rate-limited."""


class GeminiProvider(VisionProvider):
    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash"):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def analyze(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "landmark",
        context: str = "",
        max_retries: int = 3,
    ) -> VisionResult:
        """Send an image to Gemini and parse the result. Retries on transient 429s."""
        from google.genai import types
        from post_trip_summary.vision.prompts import get_prompt

        prompt = get_prompt(purpose, context=context)
        contents = [
            types.Part.from_bytes(data=image_data, mime_type=media_type),
            types.Part.from_text(text=prompt),
        ]
        # Gemini 2.5+ uses thinking tokens that count against max_output_tokens.
        # Budget 1024 for thinking + 500 for the actual response.
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=1524,
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
        )

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                text = response.text
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

            except Exception as e:
                last_error = e
                error_str = str(e)

                if "429" not in error_str and "RESOURCE_EXHAUSTED" not in error_str:
                    raise

                # Check if quota is genuinely exhausted (limit: 0) vs transient rate limit
                if "limit: 0" in error_str:
                    raise QuotaExhaustedError(
                        "Gemini free tier quota exhausted. Either wait until quota resets "
                        "or enable billing at https://ai.google.dev"
                    ) from e

                # Transient rate limit — wait and retry
                if attempt < max_retries:
                    wait = min(2 ** attempt * 2, 60)
                    time.sleep(wait)

        raise last_error

    def synthesize(self, prompt: str, max_retries: int = 3) -> str:
        """Text-only call to synthesize descriptions. Retries on transient 429s."""
        from google.genai import types

        contents = [types.Part.from_text(text=prompt)]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=1024,
            thinking_config=types.ThinkingConfig(thinking_budget=512),
        )

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                text = response.text
                try:
                    data = json.loads(text)
                    return data.get("description", text)
                except json.JSONDecodeError:
                    return text

            except Exception as e:
                last_error = e
                error_str = str(e)

                if "429" not in error_str and "RESOURCE_EXHAUSTED" not in error_str:
                    raise

                if "limit: 0" in error_str:
                    raise QuotaExhaustedError(
                        "Gemini free tier quota exhausted. Either wait until quota resets "
                        "or enable billing at https://ai.google.dev"
                    ) from e

                if attempt < max_retries:
                    wait = min(2 ** attempt * 2, 60)
                    time.sleep(wait)

        raise last_error

    def estimate_cost(self, num_images: int, avg_tokens_per_image: int = 1600) -> float:
        """Gemini Flash free tier -- no cost."""
        return 0.0
