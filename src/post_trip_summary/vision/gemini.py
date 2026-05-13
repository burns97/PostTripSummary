# src/post_trip_summary/vision/gemini.py
"""Google Gemini vision provider."""
import json
import logging
import time

from post_trip_summary.vision.client import VisionProvider, VisionResult

logger = logging.getLogger(__name__)


class QuotaExhaustedError(Exception):
    """Raised when the API quota is fully exhausted (limit: 0), not just rate-limited."""


class GeminiProvider(VisionProvider):
    # Minimum seconds between API calls — free tier ~10 RPM, billing ~1000 RPM
    _MIN_INTERVAL_FREE = 7.0
    _MIN_INTERVAL_BILLING = 1.0

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.5-flash", billing: bool = False):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._billing = billing
        self._last_request = 0.0
        self._max_retries = 3 if billing else 8
        # Adaptive throttle: starts at min interval, grows on 429s
        self._interval = self._MIN_INTERVAL_BILLING if billing else self._MIN_INTERVAL_FREE

    def _throttle(self):
        """Wait if needed to respect minimum interval between requests."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last_request = time.monotonic()

    def _retry_wait(self, attempt: int) -> float:
        """Backoff time for a retry attempt, never shorter than current throttle interval."""
        if self._billing:
            base = min(2 ** attempt * 2, 60)
        else:
            base = min(2 ** attempt * 5, 90)
        return max(base, self._interval)

    def _back_off(self):
        """Widen the throttle interval after a rate-limit hit."""
        max_interval = 60.0
        new_interval = min(self._interval * 1.5, max_interval)
        if new_interval != self._interval:
            self._interval = new_interval
            logger.info("Rate limited — throttle interval increased to %.0fs", self._interval)

    def analyze(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "landmark",
        context: str = "",
        max_retries: int | None = None,
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

        retries = max_retries if max_retries is not None else self._max_retries
        last_error = None
        for attempt in range(retries + 1):
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

                # Transient rate limit — widen throttle and retry
                self._back_off()
                if attempt < retries:
                    wait = self._retry_wait(attempt)
                    time.sleep(wait)

        raise last_error

    def synthesize(self, prompt: str, max_retries: int | None = None) -> str:
        """Text-only call to synthesize descriptions. Retries on transient 429s."""
        from google.genai import types

        contents = [types.Part.from_text(text=prompt)]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=1024,
            thinking_config=types.ThinkingConfig(thinking_budget=512),
        )

        retries = max_retries if max_retries is not None else self._max_retries
        last_error = None
        for attempt in range(retries + 1):
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

                self._back_off()
                if attempt < retries:
                    wait = self._retry_wait(attempt)
                    time.sleep(wait)

        raise last_error

    def analyze_montage(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "montage",
        context: str = "",
        image_count: int = 0,
        max_retries: int | None = None,
        **prompt_kwargs,
    ) -> dict:
        """Analyze a montage image.

        For purpose='montage': returns {'summary': str, 'highlights': list}.
        For other purposes (e.g. 'batch_describe'): returns raw parsed JSON dict.
        """
        from google.genai import types
        from post_trip_summary.vision.prompts import get_prompt

        prompt = get_prompt(purpose, context=context, image_count=image_count, **prompt_kwargs)
        contents = [
            types.Part.from_bytes(data=image_data, mime_type=media_type),
            types.Part.from_text(text=prompt),
        ]
        # Batch calls with many photos need more response tokens
        output_tokens = 3072 if purpose == "batch_describe" else 1524
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=output_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
        )

        retries = max_retries if max_retries is not None else self._max_retries
        last_error = None
        for attempt in range(retries + 1):
            self._throttle()
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                text = response.text
                data = json.loads(text)
                if purpose == "montage":
                    return {
                        "summary": data.get("summary", ""),
                        "highlights": data.get("highlights", []),
                    }
                return data

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

                self._back_off()
                if attempt < retries:
                    wait = self._retry_wait(attempt)
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
