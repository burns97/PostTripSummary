# src/post_trip_summary/vision/gemini.py
"""Google Gemini vision provider."""
import json

from post_trip_summary.vision.client import VisionProvider, VisionResult


class GeminiProvider(VisionProvider):
    def __init__(self, api_key: str | None = None, model: str = "gemini-2.0-flash"):
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def analyze(
        self,
        image_data: bytes,
        media_type: str = "image/jpeg",
        purpose: str = "landmark",
    ) -> VisionResult:
        """Send an image to Gemini and parse the result."""
        from google.genai import types
        from post_trip_summary.vision.prompts import get_prompt

        prompt = get_prompt(purpose)

        response = self._client.models.generate_content(
            model=self._model,
            contents=[
                types.Part.from_bytes(data=image_data, mime_type=media_type),
                types.Part.from_text(text=prompt),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=500,
            ),
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

    def estimate_cost(self, num_images: int, avg_tokens_per_image: int = 1600) -> float:
        """Gemini Flash free tier -- no cost."""
        return 0.0
