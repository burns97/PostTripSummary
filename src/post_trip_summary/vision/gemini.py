# src/post_trip_summary/vision/gemini.py
"""Google Gemini vision provider."""
import json
import time

from post_trip_summary.vision.client import VisionProvider, VisionResult


class QuotaExhaustedError(Exception):
    """Raised when the API quota is fully exhausted (limit: 0), not just rate-limited."""


class GeminiProvider(VisionProvider):
    # Minimum seconds between API calls to avoid 503 overload errors
    _MIN_INTERVAL = 1.0

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash", billing: bool = False):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._billing = billing
        self._last_request = 0.0

    def _throttle(self):
        """Wait if needed to respect minimum interval between requests."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._MIN_INTERVAL:
            time.sleep(self._MIN_INTERVAL - elapsed)
        self._last_request = time.monotonic()

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
            self._throttle()
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

                err_lower = error_str.lower()
                retryable = "429" in err_lower or "resource_exhausted" in err_lower or "503" in err_lower or "overloaded" in err_lower
                if not retryable:
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
            self._throttle()
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

                err_lower = error_str.lower()
                retryable = "429" in err_lower or "resource_exhausted" in err_lower or "503" in err_lower or "overloaded" in err_lower
                if not retryable:
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

    def analyze_montage(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "montage",
        context: str = "",
        image_count: int = 0,
        max_retries: int = 3,
    ) -> dict:
        """Analyze a montage image. Returns dict with 'summary' and 'highlights' keys."""
        from google.genai import types
        from post_trip_summary.vision.prompts import get_prompt

        prompt = get_prompt(purpose, context=context, image_count=image_count)
        contents = [
            types.Part.from_bytes(data=image_data, mime_type=media_type),
            types.Part.from_text(text=prompt),
        ]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=1524,
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
        )

        last_error = None
        for attempt in range(max_retries + 1):
            self._throttle()
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                text = response.text
                data = json.loads(text)
                return {
                    "summary": data.get("summary", ""),
                    "highlights": data.get("highlights", []),
                }

            except Exception as e:
                last_error = e
                error_str = str(e)

                err_lower = error_str.lower()
                retryable = "429" in err_lower or "resource_exhausted" in err_lower or "503" in err_lower or "overloaded" in err_lower
                if not retryable:
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

    # Per-model pricing (per 1M tokens): {model_prefix: (input_cost, output_cost)}
    _PRICING = {
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-2.5-pro": (1.25, 10.00),
        "gemini-3.1-flash-lite": (0.25, 1.50),
        "gemini-3.1-pro": (2.00, 12.00),
    }

    def estimate_cost(self, num_images: int, avg_tokens_per_image: int = 1600) -> float:
        """Estimate API cost. Returns 0.0 for free tier, actual cost for paid tier."""
        if not self._billing:
            return 0.0
        # Find pricing for current model, fall back to 2.5 Flash rates
        input_rate, output_rate = self._PRICING.get(self._model, (0.30, 2.50))
        input_tokens = num_images * avg_tokens_per_image
        output_tokens = num_images * 200
        input_cost = (input_tokens / 1_000_000) * input_rate
        output_cost = (output_tokens / 1_000_000) * output_rate
        return round(input_cost + output_cost, 4)
