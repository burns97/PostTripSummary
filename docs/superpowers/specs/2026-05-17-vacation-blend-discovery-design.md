# Vacation Blend Discovery

**Date:** 2026-05-17
**Status:** Draft for review

## Summary

Vacation Blend Discovery adds a lightweight intelligence layer that determines what kind of trip the user took before the app generates narrative or curates the final Trip Story. The output is a reviewable set of trip themes, confidence, and evidence. It does not yet change photo selection, event inclusion, story density, or Trip Story rendering.

The product goal is to move beyond a generic "best photos" workflow. Different vacations need different editorial strategies. A New Zealand road trip should preserve route progression, hikes, landscapes, and movement. A Las Vegas friends trip should emphasize people, nightlife, meals, shows, and social energy. A beach vacation should compress repeated relaxation scenes and surface the strongest mood-setting moments. The app should infer that blend early, expose the main themes for correction, and persist the result for later phases.

## Product Goal

After the trip timeline has been created and reviewed, the app should present a short discovery result:

> This looks like an **Adventure + Road Trip** story.
>
> Also detected: Food, Culture, Scenic Drives.

The user can remove wrong primary themes, promote secondary themes, or add a missing theme from a controlled list. During development, the app should also expose internal evidence and analysis details so the algorithm can be debugged and improved.

## Non-Goals

This phase does not:

- Change which photos are kept.
- Change which photos are highlights.
- Change event inclusion or event ordering in Trip Story.
- Change story density, length, or layout.
- Generate the final narrative prose.
- Require local AI hardware.
- Require cloud vision calls.
- Replace the existing enrichment pipeline.
- Add a full recommendation engine.

The only durable behavior change is that a session can produce and persist a Vacation Blend result for later use.

## User Experience

### User-Facing Flow

Vacation Blend becomes a user-facing Discovery step after timeline review and before enrichment.

1. User imports photos and optional supplementary data.
2. App builds and names the timeline.
3. User reviews/corrects the timeline.
4. App runs Vacation Blend Discovery.
5. User sees primary themes and secondary themes.
6. User can correct theme chips.
7. App saves the accepted blend.
8. Existing enrichment and highlight review continue normally.

The UI should not expose percentages to the normal user. It should show simple theme chips:

- Primary themes: prominent selected chips.
- Secondary themes: smaller suggested chips.
- Add themes: controlled list of available categories.
- Remove themes: X/remove action on selected chips.

### Development View

During development, the Discovery screen should include an expandable diagnostics panel:

- Analysis mode.
- Metadata signals used.
- Optional local model name and runtime.
- Optional cloud provider/model and estimated cost.
- Sample size.
- Theme scores.
- Confidence.
- Evidence strings.
- Warnings.

This panel is for debugging product quality. It should be easy to hide or remove from a future consumer-facing version.

## Theme Taxonomy

Use a controlled theme taxonomy rather than free-form labels. This keeps the UI understandable and makes future story logic deterministic.

Initial theme IDs:

| ID | User Label | Description |
| --- | --- | --- |
| `road_trip` | Road Trip | Frequent movement, scenic drives, many stops, changing locations |
| `adventure_outdoors` | Adventure | Hiking, boats, viewpoints, rugged terrain, active outdoor travel |
| `nature_wildlife` | Nature & Wildlife | Landscapes, animals, parks, gardens, natural features |
| `culture_sightseeing` | Culture & Sightseeing | Museums, architecture, historic sites, landmarks, neighborhoods |
| `food_drink` | Food & Drink | Restaurants, markets, cafes, wineries, breweries, cooking |
| `people_social` | People & Friends | Group photos, friends, family, social moments, portraits |
| `nightlife_events` | Nightlife & Events | Clubs, casinos, concerts, shows, evening venues, parties |
| `beach_relaxation` | Beach & Relaxation | Beach, pool, sun, slow days, resort downtime |
| `resort_luxury` | Resort & Luxury | Hotels, suites, spas, amenities, fine dining, premium experiences |
| `family_milestone` | Family & Milestones | Kids, reunions, anniversaries, birthdays, ceremonies |

The taxonomy should be stored centrally so prompts, tests, UI labels, and later curation rules all refer to the same IDs.

## Data Contract

Add a new discovery data model rather than mutating `Trip`, `Day`, `Event`, or `Photo`.

Proposed dataclasses live in a new discovery-focused module:

```python
@dataclass
class ThemeScore:
    theme_id: str
    score: float
    confidence: str  # "low", "medium", "high"
    evidence: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)  # metadata, local_vision, cloud


@dataclass
class VacationBlend:
    primary_themes: list[str]
    secondary_themes: list[str]
    rejected_themes: list[str]
    confidence: str
    evidence: list[str]
    theme_scores: list[ThemeScore]
    analysis_mode: str
    sample_size: int = 0
    local_model: str | None = None
    cloud_model: str | None = None
    estimated_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)
```

Persist the accepted blend separately from the trip model:

```text
<session_dir>/vacation_blend.json
```

This avoids broad serialization risk and keeps the feature reversible. Later phases can choose whether to fold the accepted blend into a richer story configuration model.

## Analysis Modes

Vacation Blend Discovery supports four modes:

| Mode | Behavior |
| --- | --- |
| `metadata_only` | Uses trip timeline, GPS, event names/types, POI names, timestamps, and photo counts |
| `local_assisted` | Metadata plus optional local vision tags from sampled images |
| `cloud_assisted` | Metadata plus cloud synthesis, optionally with a small vision sample |
| `hybrid` | Metadata, optional local tags, and cloud synthesis from compact evidence |

The first implementation should default to `metadata_only` unless cloud discovery is explicitly enabled. Local vision should be optional and experimental. Cloud synthesis should remain cost-gated.

## Metadata Discovery Algorithm

The deterministic metadata pass should run first and always be available. It should produce theme scores and evidence from existing trip data.

Inputs:

- Trip date range and duration.
- Number of days.
- Number of events.
- Event types.
- Event names and location names.
- City/country counts.
- GPS availability.
- Approximate movement between event centroids.
- Time-of-day distribution.
- Photos per day and photos per event.
- Kept/highlight counts when available.
- POI/category keywords from geocoding and event names.

Signals:

- High distinct-location count and frequent movement increase `road_trip`.
- Hiking/trail/park/viewpoint/natural-feature names increase `adventure_outdoors` and `nature_wildlife`.
- Museum/landmark/historic/architecture/neighborhood names increase `culture_sightseeing`.
- Restaurant/cafe/bar/market/winery/brewery names increase `food_drink`.
- Late-night event timing plus casino/club/show/concert/bar terms increase `nightlife_events`.
- Beach/pool/resort/spa terms and repeated same-location days increase `beach_relaxation` and `resort_luxury`.
- Photo bursts around people-heavy events cannot be reliably detected from metadata alone, so `people_social` and `family_milestone` should usually require local/cloud visual evidence or explicit user selection.

The metadata pass should produce conservative evidence. It should prefer "medium confidence" over pretending certainty when the signal is weak.

## Optional Local Vision Pass

Local AI is an optional accelerator, not a required dependency.

Given the current target hardware is a Windows laptop with 16 GB RAM, the design should assume local vision may be slow, unavailable, or low quality. The app should support local inference through a pluggable adapter only when configured.

Local vision responsibilities:

- Analyze sampled, resized images.
- Return structured JSON tags.
- Avoid writing final prose.
- Avoid deciding final story inclusion.
- Cache results by file hash, model name, and prompt version.

Example local tag result:

```json
{
  "photo_id": "day03-event04-photo02",
  "scene": "hiking trail with mountain view",
  "themes": ["adventure_outdoors", "nature_wildlife"],
  "people_present": false,
  "indoor_outdoor": "outdoor",
  "activity_level": "high",
  "confidence": "medium"
}
```

Local provider requirements:

- Must be optional in settings.
- Must fail closed with a warning and fall back to metadata-only.
- Must have a timeout per image or batch.
- Must validate JSON before using output.
- Must not block the user from continuing if unavailable.

The first adapter should call a local HTTP endpoint rather than embedding model-specific runtime code. This allows experimentation with Ollama, LM Studio, or another runtime without making the app responsible for installing or managing model weights.

## Optional Cloud Synthesis

Cloud synthesis should take compact evidence and return a normalized `VacationBlend`. It should not receive all trip photos.

Inputs:

- Metadata summary.
- Theme scores from deterministic pass.
- Local vision tag summary if available.
- A limited sample of image descriptions/tags if local vision was run.
- Existing event names and locations.

Output must be strict JSON matching the `VacationBlend` contract.

Cloud synthesis is valuable when:

- Metadata signals conflict.
- The trip type depends on visual semantics.
- The app needs to distinguish similar patterns, such as beach relaxation vs. active coastal adventure.
- The user explicitly chooses higher-quality discovery.

Cloud synthesis should be skipped when:

- No API key is configured.
- Cost is not approved.
- Metadata confidence is already high and local tags agree.

## Sampling Strategy

Sampling must represent the whole trip while keeping local and cloud analysis practical.

For v1:

- Sample after skeleton review, using reviewed events.
- Use kept photos only.
- Prefer highlighted photos if highlights already exist; otherwise use quality score and temporal spread.
- Cap local vision at 150 photos by default.
- Cap cloud vision sample at 40 photos by default if cloud images are ever used.
- Always distribute samples across days before filling extra slots.
- Prefer 1-3 photos per event.
- Include high-photo-count events, unique locations, and high-quality photos.
- Avoid oversampling repeated scenes from the same event.

The sampler should return both selected photos and a reason for each sample:

```json
{
  "photo_id": "day05-event02-photo03",
  "reason": "highest_quality_for_event"
}
```

This makes diagnostics and future tests much easier.

## Pipeline Placement

Add Discovery as a stage between reviewed timeline and enrichment:

```text
new -> setup -> ingested -> reviewed -> discovered -> enriched -> highlights_done -> generated
```

Rationale:

- The timeline should be reviewed first because wrong event names/locations weaken discovery.
- Enrichment should happen after discovery because later enrichment prompts can eventually use the accepted blend.
- The accepted blend should be available before highlight review and Trip Story generation.

For CLI compatibility, Phase 2A should also provide a standalone command:

```powershell
post-trip-summary discover <slug>
```

This keeps discovery testable outside the browser wizard and gives a simple way to rerun the blend after editing timeline data.

## Browser Review UI

The Discovery page should be simple:

- Header: "Trip Discovery"
- Summary sentence: "This looks like a Road Trip + Adventure story."
- Primary theme chips.
- Secondary detected chips.
- Add theme dropdown/list.
- Remove chip action.
- Continue button.
- Developer diagnostics disclosure.

The page should not be a dashboard. It should feel like the app is asking for a quick taste correction before writing the story.

Suggested copy:

```text
We analyzed the trip timeline and a sample of photos to understand the flavor of this trip.

Primary themes
[Road Trip] [Adventure]

Also detected
[Food & Drink] [Culture & Sightseeing] [Nature & Wildlife]
```

If confidence is low:

```text
We found a few possible themes, but the signal is mixed. Adjust these before continuing.
```

If local/cloud analysis was unavailable:

```text
Discovery used timeline and location data only. You can still adjust the themes.
```

## Settings

Add discovery defaults to `DEFAULT_SETTINGS` and store the effective settings per session:

```json
{
  "discovery": {
    "mode": "metadata_only",
    "enable_local_ai": false,
    "local_provider_url": null,
    "local_model": null,
    "enable_cloud_synthesis": false,
    "max_local_images": 150,
    "max_cloud_images": 40,
    "timeout_seconds": 30
  }
}
```

Default should be safe:

- `mode`: `metadata_only`
- local AI disabled
- cloud synthesis disabled

This avoids surprising cost or laptop performance problems.

Global settings can eventually provide machine-level defaults for local/cloud providers, but Phase 2A should keep runtime behavior controlled by session settings.

## Cost and Privacy

Discovery should preserve the current project principle: vision API calls cost money, so estimate and gate them.

Rules:

- Metadata discovery is always free.
- Local discovery is free but may be slow; show runtime/progress.
- Cloud synthesis must show estimated image count and cost before running.
- Cloud image calls should be capped and optional.
- The app should clearly report what mode was used.

Privacy posture:

- Metadata-only and local-assisted modes keep photos local.
- Cloud-assisted mode may send selected image samples or compact tags depending on configuration.
- Future consumer product copy should avoid deep technical detail, but development diagnostics should remain explicit.

## Failure Behavior

Discovery should never block the whole trip pipeline.

Failure cases:

- No photos: produce low-confidence metadata result from event names/locations.
- No GPS: rely on event names, timestamps, and optional vision.
- Local model unavailable: warn and continue metadata-only.
- Local model emits invalid JSON: ignore invalid result, record warning, continue.
- Cloud API missing or declined: continue without cloud synthesis.
- Cloud API failure: preserve metadata/local result and warning.
- No strong themes: produce low-confidence empty or broad blend and require user correction.

## Testing Strategy

Unit tests:

- Theme taxonomy contains stable IDs and labels.
- Metadata scoring detects obvious road-trip signals.
- Metadata scoring detects obvious beach/resort signals from POI names.
- Metadata scoring detects culture/food/nightlife keywords.
- Weak metadata produces low or medium confidence, not high confidence.
- Sampler distributes photos across days.
- Sampler respects max image caps.
- Local tag parser rejects malformed JSON safely.
- VacationBlend serializes and deserializes without touching `Trip`.

Integration tests:

- Discovery artifact is saved to `vacation_blend.json`.
- Wizard can advance from reviewed to discovered.
- Discovery page renders primary/secondary themes.
- User edits primary/secondary themes and saves.
- Missing local/cloud providers fall back without crashing.

No tests in this phase should require a real local model or real cloud API. Provider tests should use fakes.

## Implementation Shape

Likely new modules:

```text
src/post_trip_summary/discovery/
  __init__.py
  models.py
  taxonomy.py
  metadata.py
  sampling.py
  local_provider.py
  cloud_synthesis.py
  service.py
  serialization.py
```

Likely modified modules:

```text
src/post_trip_summary/config.py
src/post_trip_summary/server/app.py
src/post_trip_summary/cli.py
src/post_trip_summary/templates/
tests/
```

Keep dependencies pointed inward:

- Discovery may depend on `models.py`.
- Discovery should not depend on Trip Story output.
- Trip Story may later depend on accepted discovery results, but not in this phase.
- Local/cloud providers should be adapters behind a small interface.

## Development Phasing

### Phase 2A: Metadata-Only Discovery

- Add taxonomy.
- Add `VacationBlend` models.
- Add metadata scoring.
- Persist artifact.
- Add basic browser review page.
- Add `post-trip-summary discover <slug>` for CLI/debug use.
- Add tests.

This creates useful product behavior without cloud cost or local hardware risk.

### Phase 2B: Optional Local Vision Tags

- Add local provider interface.
- Add sample selection.
- Add local JSON tag parser and cache.
- Add diagnostics.
- Keep default disabled.

This lets the Windows laptop experiment answer whether local vision is worthwhile.

### Phase 2C: Optional Cloud Synthesis

- Add cloud synthesis prompt and strict JSON parsing.
- Add cost estimate/gate.
- Use compact metadata/local evidence first.
- Use image sample only if explicitly enabled.

This improves quality without requiring the app to send thousands of photos.

## Success Criteria

Vacation Blend Discovery is successful when:

- The app can produce a plausible primary/secondary theme set for a completed timeline.
- The user can correct the detected themes in the browser.
- The result is saved and reloadable.
- No paid API is required for the default path.
- Local AI can be attempted without making the whole app fragile.
- Cloud synthesis is cost-gated and optional.
- Existing Trip Story generation remains unchanged.
- Tests cover deterministic scoring, persistence, review edits, and fallback behavior.

## Decisions Made While User Was Away

I made these design calls to keep the spec concrete:

1. **Discovery is a separate stage after reviewed timeline and before enrichment.**
   This gives the blend a clear place in the workflow and makes it available to future enrichment and story-generation phases.

2. **The default mode is metadata-only.**
   This avoids requiring local hardware or paid cloud APIs before the feature is useful.

3. **Local AI is an optional HTTP adapter, not an embedded runtime.**
   This keeps the app from owning model installation and allows experimentation with whatever local runtime works best.

4. **Vacation Blend is persisted separately from `Trip`.**
   This avoids changing core trip serialization and keeps the feature easy to revise.

5. **This phase stops before recommendations.**
   Photo/event inclusion, story density, and curation rules are intentionally deferred until the blend itself is trustworthy.

## Approval Needed

Please review these before implementation planning:

1. Confirm whether adding an internal `discovered` stage is acceptable, or whether Discovery should be artifact-only without changing the stage list.
2. Confirm whether the initial taxonomy is broad enough, especially whether `family_milestone` should remain a theme even though it may be hard to infer without faces/people context.
3. Confirm whether the first implementation should include only Phase 2A metadata discovery, or include the local-provider skeleton in the same implementation plan.
