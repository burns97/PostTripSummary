# src/post_trip_summary/vision/prompts.py
"""Prompt templates for vision API calls."""

PURPOSES = ("landmark", "sign", "scene")

_PROMPTS = {
    "landmark": """Analyze this photo and identify any landmarks or notable locations.

Respond with JSON only:
{
  "description": "Brief description of what's in the photo",
  "landmark": "Name of the landmark if identifiable, or null",
  "confidence": "high/medium/low"
}""",

    "sign": """Read any visible text in this photo -- signs, menus, storefronts, plaques, street names.

Respond with JSON only:
{
  "description": "Brief description of the sign or text context",
  "text_found": "The text you can read, or null if none visible",
  "confidence": "high/medium/low"
}""",

    "scene": """Describe this vacation photo briefly for a trip journal. Focus on what's happening, who/what is visible, and the setting.

Respond with JSON only:
{
  "description": "2-3 sentence description suitable for a trip journal",
  "landmark": "Name of any recognizable landmark, or null",
  "text_found": "Any readable text in the image, or null",
  "confidence": "high/medium/low"
}""",
}


def get_prompt(purpose: str) -> str:
    """Get the prompt template for a given purpose."""
    if purpose not in _PROMPTS:
        raise ValueError(f"Unknown purpose: {purpose}. Must be one of: {PURPOSES}")
    return _PROMPTS[purpose]
