"""Ollama local vision provider."""
from __future__ import annotations

import base64
from io import BytesIO
import json
from typing import Callable
from urllib import error, request

from post_trip_summary.vision.client import VisionProvider, VisionResult

Transport = Callable[[str, dict, int], dict]


class OllamaProviderError(Exception):
    """Raised when the local Ollama service cannot complete a request."""


class OllamaProvider(VisionProvider):
    """Vision provider for local multimodal models served by Ollama."""

    def __init__(
        self,
        model: str = "gemma4:e2b",
        base_url: str = "http://localhost:11434",
        timeout_seconds: int = 120,
        transport: Transport | None = None,
    ):
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = int(timeout_seconds)
        self._transport = transport or self._default_transport

    def analyze(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "landmark",
        context: str = "",
    ) -> VisionResult:
        """Analyze one image with Ollama and return a normalized result."""
        from post_trip_summary.vision.prompts import get_prompt

        prompt = get_prompt(purpose, context=context)
        image_data = _normalize_image_for_ollama(image_data, media_type)
        text = self._generate(prompt, image_data=image_data)
        data = _parse_json_object(text)
        if data is None:
            return VisionResult(description=text)
        return VisionResult(
            description=str(data.get("description", "")),
            landmark=data.get("landmark"),
            text_found=data.get("text_found"),
            confidence=str(data.get("confidence", "medium")),
        )

    def analyze_montage(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "montage",
        context: str = "",
        image_count: int = 0,
        **prompt_kwargs,
    ) -> dict:
        """Analyze a montage image and return parsed JSON from Ollama."""
        from post_trip_summary.vision.prompts import get_prompt

        prompt = get_prompt(purpose, context=context, image_count=image_count, **prompt_kwargs)
        image_data = _normalize_image_for_ollama(image_data, media_type)
        text = self._generate(prompt, image_data=image_data)
        data = _parse_json_object(text)
        if data is None:
            if purpose == "montage":
                return {"summary": text, "highlights": []}
            return {}
        if purpose == "montage":
            return {
                "summary": data.get("summary", ""),
                "highlights": data.get("highlights", []),
            }
        return data

    def synthesize(self, prompt: str) -> str:
        """Run a text-only synthesis prompt through Ollama."""
        text = self._generate(prompt)
        data = _parse_json_object(text)
        if data is None:
            return text
        return str(data.get("description", text))

    def estimate_cost(self, num_images: int, avg_tokens_per_image: int = 1600) -> float:
        """Local Ollama calls have no metered API cost."""
        return 0.0

    def _generate(self, prompt: str, image_data: bytes | None = None) -> str:
        payload: dict[str, object] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        if image_data is not None:
            payload["images"] = [base64.b64encode(image_data).decode("ascii")]

        try:
            data = self._transport(f"{self._base_url}/api/generate", payload, self._timeout_seconds)
        except OllamaProviderError as exc:
            raise OllamaProviderError(
                f"Ollama request failed at {self._base_url}: {exc}"
            ) from exc
        except Exception as exc:
            raise OllamaProviderError(
                f"Could not reach Ollama at {self._base_url}. "
                "Start Ollama and make sure the configured model is available."
            ) from exc

        response = data.get("response", "")
        return str(response).strip()

    @staticmethod
    def _default_transport(url: str, payload: dict, timeout: int) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise OllamaProviderError(f"Ollama request failed: {exc}") from exc


def _normalize_image_for_ollama(image_data: bytes, media_type: str) -> bytes:
    """Convert formats Ollama may not decode, such as HEIC/TIFF, to JPEG."""
    normalized_media_type = media_type.lower()
    if normalized_media_type in ("image/jpeg", "image/jpg", "image/png"):
        return image_data

    if normalized_media_type in ("image/heic", "image/heif"):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError as exc:
            raise OllamaProviderError(
                "Ollama cannot decode HEIC/HEIF directly and pillow-heif is not installed."
            ) from exc

    try:
        from PIL import Image

        with Image.open(BytesIO(image_data)) as img:
            output = BytesIO()
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=90)
            return output.getvalue()
    except Exception as exc:
        raise OllamaProviderError(
            f"Ollama cannot decode {media_type} directly and conversion to JPEG failed."
        ) from exc


def _parse_json_object(text: str) -> dict | None:
    """Parse a JSON object, tolerating surrounding model chatter."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None
