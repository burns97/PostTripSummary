# src/post_trip_summary/vision/prompts.py
"""Prompt templates for vision API calls."""

PURPOSES = ("landmark", "sign", "scene", "synthesize", "montage", "narrative")

_PROMPTS = {
    "landmark": """Analyze this photo and identify any landmarks or notable locations.
{context}
Respond with JSON only:
{{
  "description": "Brief description of what's in the photo",
  "landmark": "Name of the landmark if identifiable, or null",
  "confidence": "high/medium/low"
}}""",

    "sign": """Read any visible text in this photo -- signs, menus, storefronts, plaques, street names.
{context}
Respond with JSON only:
{{
  "description": "Brief description of the sign or text context",
  "text_found": "The text you can read, or null if none visible",
  "confidence": "high/medium/low"
}}""",

    "scene": """Describe this vacation photo briefly for a trip journal. Focus on what's happening, who/what is visible, and the setting.
{context}
Respond with JSON only:
{{
  "description": "2-3 sentence description suitable for a trip journal",
  "landmark": "Name of any recognizable landmark, or null",
  "text_found": "Any readable text in the image, or null",
  "confidence": "high/medium/low"
}}""",

    "synthesize": """Here are descriptions of {image_count} photos from the same event during a vacation trip:

{descriptions}
{context}
Write a unified 2-4 sentence paragraph for a trip journal that synthesizes these photo descriptions into a cohesive account of this event. Do not list each photo separately — blend them into a natural narrative.

Respond with JSON only:
{{
  "description": "Unified 2-4 sentence paragraph for a trip journal"
}}""",

    "montage": """Here are {image_count} photos from a single event during a vacation trip, shown as a numbered grid.
{context}
Describe what was seen and done across these photos. Focus on the overall experience, not individual photos. 2-3 sentences, suitable for a trip summary.

Also pick up to 5 of the most interesting/representative photos by their grid number.

Respond with JSON only:
{{
  "summary": "factual 2-3 sentence summary of the event",
  "highlights": [3, 7, 12]
}}""",

    "narrative": """Here is a factual summary of an event, plus detailed descriptions of key photos:

Summary: {montage_summary}

Photo details:
{descriptions}
{context}
Write a 3-5 sentence journal-style narrative that brings this event to life. Blend the overview with specific details from the photos.

Respond with JSON only:
{{
  "narrative": "journal-style paragraph"
}}""",
}


def build_context(
    timestamp: str = "",
    city: str = "",
    country: str = "",
    poi_name: str = "",
    event_name: str = "",
) -> str:
    """Build a context hint string from available metadata."""
    parts = []
    if event_name and event_name not in ("Unknown", poi_name, city):
        parts.append(f"Event: {event_name}")
    if timestamp:
        parts.append(f"Taken: {timestamp}")
    location_parts = [p for p in [poi_name, city, country] if p]
    if location_parts:
        parts.append(f"Location: {', '.join(location_parts)}")
    if not parts:
        return ""
    return "\nContext from photo metadata:\n" + "\n".join(f"  {p}" for p in parts) + "\n"


def get_prompt(purpose: str, context: str = "", **kwargs) -> str:
    """Get the prompt template for a given purpose, with optional context."""
    if purpose not in _PROMPTS:
        raise ValueError(f"Unknown purpose: {purpose}. Must be one of: {PURPOSES}")
    return _PROMPTS[purpose].format(context=context, **kwargs)
