# Ollama Vision Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an experimental Ollama-backed vision provider that can run local models such as `gemma4:e2b` through the existing enrichment pipeline.

**Architecture:** Add a focused `OllamaProvider` module and wire it into settings and the provider factory. The existing enrichment flow remains provider-agnostic, with a small settings flag for providers that do not require API keys.

**Tech Stack:** Python 3.10, standard-library `urllib.request`, pytest, existing `VisionProvider` abstraction.

---

### Task 1: Settings and Factory

**Files:**
- Modify: `src/post_trip_summary/settings.py`
- Modify: `src/post_trip_summary/vision/client.py`
- Test: `tests/test_settings.py`
- Test: `tests/test_vision_client.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert `provider = "ollama"` returns `api_key is None`, `requires_api_key is False`, model/base URL/timeout values, and that `create_provider("ollama")` returns an `OllamaProvider`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_settings.py::test_get_vision_settings_ollama tests/test_vision_client.py::test_create_provider_ollama -v`

- [ ] **Step 3: Implement minimal settings and factory support**

Add Ollama defaults, default TOML comments, `get_vision_settings()` branch, and factory branch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_settings.py::test_get_vision_settings_ollama tests/test_vision_client.py::test_create_provider_ollama -v`

### Task 2: Ollama Provider

**Files:**
- Create: `src/post_trip_summary/vision/ollama.py`
- Test: `tests/test_ollama_provider.py`

- [ ] **Step 1: Write failing provider tests**

Cover JSON response parsing for `analyze`, montage response passthrough for `analyze_montage`, text synthesis, invalid JSON fallback, zero cost, and HTTP error wrapping.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ollama_provider.py -v`

- [ ] **Step 3: Implement provider**

Implement request payload construction, image base64 encoding, response parsing, and `OllamaProviderError`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ollama_provider.py -v`

### Task 3: Enrichment Gate

**Files:**
- Modify: `src/post_trip_summary/pipeline/enrich.py`
- Test: `tests/test_enrich.py`
- Test: `tests/test_enrich_montage.py`

- [ ] **Step 1: Write failing tests**

Add tests proving `provider = "ollama"` does not skip enrichment when no API key is present for both CLI and headless paths.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_enrich.py::test_enrich_ollama_does_not_require_api_key tests/test_enrich_montage.py::TestQuickMode::test_headless_ollama_does_not_require_api_key -v`

- [ ] **Step 3: Implement provider-key gate**

Use `requires_api_key` from settings, defaulting to `True` for backward compatibility.

- [ ] **Step 4: Run tests to verify they pass**

Run the same targeted pytest command.

### Task 4: Documentation and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document Ollama setup**

Add a short experimental Ollama provider section showing `provider = "ollama"`, `ollama_model = "gemma4:e2b"`, and `ollama_base_url = "http://localhost:11434"`.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_ollama_provider.py tests/test_vision_client.py tests/test_settings.py tests/test_enrich.py tests/test_enrich_montage.py -v`

- [ ] **Step 3: Run full tests**

Run: `python -m pytest`
