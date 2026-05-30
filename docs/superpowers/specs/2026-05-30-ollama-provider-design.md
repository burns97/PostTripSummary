# Ollama Vision Provider Design

**Date:** 2026-05-30
**Status:** Approved by delegation

## Problem

PostTripSummary can use Gemini and Claude for vision enrichment, but local open-source vision models run through Ollama are not first-class providers. This prevents cheap experimental front-loading of photo descriptions and makes local tests require ad hoc scripts outside the app.

## Goals

1. Add an experimental `ollama` vision provider that fits the existing `VisionProvider` abstraction.
2. Support image analysis, montage analysis, and text synthesis through Ollama's local HTTP API.
3. Make local use opt-in through settings or environment variables, with zero cost estimates.
4. Keep Gemini as the default quality path and avoid changing enrichment behavior unless `provider = "ollama"`.

## Non-Goals

- No quality ranking between Ollama and Gemini.
- No background model download or Ollama process management.
- No new dependencies beyond Python standard library.
- No GPU or hardware tuning logic.

## Architecture

Create `post_trip_summary.vision.ollama.OllamaProvider` implementing `VisionProvider`. It will call `POST /api/generate` on the configured Ollama host, sending the prompt and base64-encoded image for image-backed calls. Responses are parsed as JSON when possible and tolerated as plain text otherwise, matching the existing cloud providers' behavior.

`settings.py` will add `ollama_model`, `ollama_base_url`, and `ollama_timeout_seconds`. `get_vision_settings()` will return those values for `provider = "ollama"` without requiring an API key.

`create_provider()` will instantiate `OllamaProvider` for `name == "ollama"`. Existing enrichment code checks for missing API keys, so it must treat providers that do not need keys differently. The small change is to introduce a `requires_api_key` flag in settings output.

## Data Flow

1. Settings select `provider = "ollama"` and a model such as `gemma4:e2b`.
2. Enrichment calls `create_provider("ollama", ...)`.
3. `OllamaProvider.analyze()` builds the existing prompt with context, sends one image to Ollama, and maps the JSON response into `VisionResult`.
4. `OllamaProvider.analyze_montage()` sends the montage image and returns the parsed JSON object used by quick/thorough enrichment.
5. `OllamaProvider.synthesize()` sends a text-only prompt and returns either the JSON `description` field or raw text.

## Error Handling

- Connection failures, timeouts, and HTTP errors raise `OllamaProviderError` with actionable text.
- JSON parsing falls back to plain descriptions so weaker local models can still produce useful output.
- Enrichment catches provider exceptions in the existing per-event fallback paths.

## Testing

- Unit-test request payloads and response parsing with a fake HTTP transport.
- Unit-test non-JSON fallback behavior.
- Unit-test settings output for `provider = "ollama"`.
- Unit-test provider factory behavior.
- Unit-test enrichment's no-API-key gate does not skip Ollama.

## Validation

This design follows the existing provider boundary and avoids touching the expensive enrichment strategy. Local model use is experimental, opt-in, and reversible by changing one setting back to `gemini`.
