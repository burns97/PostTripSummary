# Product Foundation: Shareable Story First

**Date:** 2026-05-16
**Status:** Draft for review

## Summary

Post-Trip Summary should evolve from an engineering-oriented trip processing pipeline into a local-first trip story studio. The core product promise is:

> Drop in your trip photos, review the draft, export a beautiful travel story.

The app should optimize for a polished, shareable trip story as the primary output while preserving the detailed archive value that motivated the original project. The existing engine remains the foundation: photos drive the timeline, GPS and geocoding name events, supplementary sources enrich context, and AI vision helps produce summaries and highlight choices.

## Product Positioning

The near-term product is a local-first application for people who take many vacation photos and want a high-quality trip recap without manually writing a blog post, sorting a photo album, or reconstructing the timeline from memory.

This is not yet a SaaS product. The app should not add accounts, billing, hosted storage, collaboration, notifications, or public link sharing in the next product iteration. Those can be revisited after the local core loop produces an excellent story.

## Primary User Promise

The user should be able to:

1. Start from a folder of trip photos.
2. Optionally add itinerary, timeline, journal, expenses, or health data.
3. Let the app build a draft timeline and story.
4. Review and correct the parts that need judgment.
5. Export a beautiful story they can share or keep.

The experience should feel like reviewing a draft travel story, not operating a pipeline.

## Primary Output: Trip Story

The primary product artifact is **Trip Story**, a polished, self-contained HTML output. It becomes the hero output in the Generate step and the target for future editor improvements.

Trip Story should be:

- Photo-forward: large imagery leads the experience.
- Editorial: reads like a travel recap, not a data report.
- Personal: includes notes, narrative, and the actual trip sequence.
- Shareable: suitable to send to friends and family as an HTML file or later as a PDF.
- Local-first: generated from local session data without requiring cloud hosting.
- Mobile-friendly: readable on phones as well as desktops.

### Trip Story Content Contract

The first version of Trip Story should include:

- Cover section with cover photo, trip title, date range, and location summary.
- Short trip introduction when AI narrative data is available.
- Route map when event coordinates are available.
- Day-by-day sections.
- Day summary when available, with fallback to event list.
- Event blocks with event name, time, location, description, notes, and highlight photos.
- Highlight gallery or reel using selected highlight photos.
- "By the Numbers" section with days, stops, photos, cities, and countries.
- Optional expenses section only when expense data exists and the user chooses to include it.

The output should gracefully degrade when data is missing. A photo-only trip should still produce a useful story.

## Secondary Outputs

Existing outputs remain valuable but become secondary:

- **Detailed Record:** personal archive with complete event details, sources, expenses, and supporting data.
- **Shareable PDF:** eventually generated from or visually aligned with Trip Story.
- **Blog Post:** export format for publishing, secondary to the primary story.
- **Photo Prep:** utility output for organized highlights and kept photos.

The Generate step should eventually present Trip Story as the default output, with secondary exports grouped under advanced or additional formats.

## Product Experience Direction

The product should move toward three user-facing phases:

1. **Import:** choose photos, optionally add data sources.
2. **Review:** inspect and correct the generated timeline/story in one workspace.
3. **Export:** preview and generate the final Trip Story and optional secondary outputs.

The current wizard stages can remain internally, but the user-facing language should shift away from "ingest", "enrich", and "generate outputs" toward "import", "review story", and "export".

## Design Direction

The visual language should be warm, editorial, and photo-forward:

- Photos carry the emotional weight.
- UI frames the story without competing with it.
- Use restrained typography and spacing appropriate for reading.
- Avoid developer-tool language in user-facing screens.
- Avoid making the product feel like a dashboard unless the workflow truly requires it.

The existing Google Stitch prompt is useful as a north star for tone and output quality, but this project should adopt it incrementally through the local-first product rather than recreating the full SaaS surface.

## Near-Term Implementation Sequence

### Phase 1: Hero Trip Story Output

Build a new Trip Story renderer using existing `Trip`, `Day`, `Event`, and `Photo` data. Add it as a new output alongside the existing outputs, then make it the primary option in the Generate step.

This phase should avoid rewriting the editor or pipeline. It should prove the target final product first.

### Phase 2: Better Narrative Generation

Add story-level narrative support:

- Trip introduction.
- Day summaries.
- Improved event narratives from highlights and source context.
- Clear fallback behavior when AI is unavailable.

### Phase 3: Unified Story Editor

Merge skeleton review, photo culling, highlight picking, notes, and description editing into one story editor workspace.

### Phase 4: Review Assistance

Add review confidence and issue queues so users focus on weak areas instead of auditing every event.

### Phase 5: Import UX Improvements

Make setup feel like choosing trip inputs, not configuring file paths. Improve validation, source guidance, recent paths, and eventually native file/folder picking.

### Phase 6: Local App Packaging

Package the browser server into a desktop-style local app once the core story loop is strong.

## Architecture Principles

- Preserve the current engine and tests.
- Add product layers incrementally instead of rewriting the pipeline.
- Keep the CLI useful for debugging and power users.
- Separate story rendering logic from existing detailed record and PDF renderers.
- Prefer small, testable renderer functions over a large template-only implementation.
- Keep generated outputs deterministic from saved session data.

## Phase 1 Design Boundary

The next implementation plan should focus only on Trip Story output. It should not include:

- Unified editor work.
- Drag-and-drop import.
- Desktop packaging.
- SaaS/auth/collaboration features.
- A full theme system.

Phase 1 may include minimal supporting helpers if needed, such as selecting a cover photo, computing a location summary, grouping highlight photos, or deriving basic day summaries from existing event descriptions.

## Success Criteria

Phase 1 is successful when:

- A user can generate `trip-story.html` from an existing final trip.
- The output feels substantially more polished and shareable than the current detailed record.
- The output works with photo-only trips and enriched trips.
- Existing outputs continue to work.
- The test suite still passes.
- The code leaves a clear path to use Trip Story as the preview target for the future unified editor.

## Phase 1 Defaults

Phase 1 should use these defaults unless later design work finds a concrete reason to change them:

- Trip Story starts as a separate output instead of replacing the current shareable summary.
- PDF export is deferred until the HTML output is strong.
- Default cover photo is the highest-quality highlighted photo, falling back to the first highlighted photo, then the first kept photo.
- Expense data is excluded from the first Trip Story output unless the implementation adds an explicit include-expenses option.
- Theme customization is deferred; Phase 1 ships one polished default theme.
