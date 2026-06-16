# Local Prefill Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in local prefill command that uses Ollama to draft representative photo descriptions before cloud enrichment.

**Architecture:** Implement a focused pipeline module that accepts an injected provider for tests and creates an Ollama provider by default. Wire it to a CLI command that saves reviewed or enriched trip data in place without stage advancement.

**Tech Stack:** Python 3.10, pytest, Click, existing `VisionProvider`, existing trip dataclasses.

---

### Task 1: Local Prefill Pipeline

**Files:**
- Create: `src/post_trip_summary/pipeline/local_prefill.py`
- Test: `tests/test_local_prefill.py`

- [ ] **Step 1: Write failing tests**

Cover: fills selected photo descriptions; skips existing descriptions; overwrite replaces existing descriptions; event summary is created from one or more descriptions; failures increment stats.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_local_prefill.py -v`

- [ ] **Step 3: Implement pipeline**

Add `LocalPrefillStats`, provider creation, event context generation, representative selection, image reading, per-photo analysis, optional local synthesis, and progress callbacks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_local_prefill.py -v`

### Task 2: CLI Command

**Files:**
- Modify: `src/post_trip_summary/cli.py`
- Test: `tests/test_cli_pipeline.py`

- [ ] **Step 1: Write failing CLI tests**

Cover reviewed-stage save, enriched-stage save, invalid stage rejection, and summary output.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli_pipeline.py::test_local_prefill_updates_reviewed_trip tests/test_cli_pipeline.py::test_local_prefill_updates_enriched_trip tests/test_cli_pipeline.py::test_local_prefill_rejects_missing_reviewed_or_enriched_data -v`

- [ ] **Step 3: Implement CLI command**

Load the correct stage file, run prefill, save back to the same file, print counts, and keep the session stage unchanged.

- [ ] **Step 4: Run CLI tests**

Run the same targeted pytest command.

### Task 3: Docs and Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document command**

Add a short local prefill example under the Ollama provider section.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_local_prefill.py tests/test_cli_pipeline.py tests/test_ollama_provider.py tests/test_enrich_montage.py -v`

- [ ] **Step 3: Run full tests**

Run: `python -m pytest`
