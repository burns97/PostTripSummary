# Future Feature: Face Recognition & Person Identification

## Context

When generating trip summaries, captions like "Karen checking out the flowers" or "Matt beside the plane" are far more engaging than generic descriptions. This feature would detect faces across all trip photos, cluster them into distinct people, let the user name the frequent ones, and feed those names into the vision API enrichment step for personalized captions.

**Status:** Brainstorm / future feature — not scheduled for implementation yet.

## Research Summary

### Library Choice: deepface

**deepface** is the recommended library for this project:
- Easy `pip install` on Windows 3.10 (no C++ compiler needed)
- MIT license (commercial use OK)
- Multiple detection backends (RetinaFace, MTCNN, YuNet, etc.)
- Generates face embeddings for cross-photo clustering
- Works on CPU (no GPU required) — ~2.5 sec/image for detection + embedding
- 15K+ GitHub stars, ~4M pip installs

**Rejected alternatives:**
- `face_recognition` (dlib): Painful Windows install, requires C++ build tools
- `insightface`: Better accuracy but pre-trained models are **non-commercial only**
- `mediapipe`: Detection only, no embeddings — can't cluster faces
- OpenCV DNN: Detection only, no embeddings
- Vision APIs (Claude/Gemini): **Cannot identify people or track across photos** by design

### Clustering Approach: DBSCAN

DBSCAN on face embeddings is the standard approach:
- No need to specify number of people in advance
- Handles outliers (strangers, partial faces) as noise
- Works well with L2 distance on 128/512-dim embeddings
- Threshold tuning: L2 distance < 1.0 typically = same person

For very large photo sets (1000+), Chinese Whispers is faster (linear time) but DBSCAN is fine for typical trip sizes (100-500 photos).

## Proposed Pipeline Integration

### New Stage: "Identify People" (between skeleton and enrich)

```
Ingest → Skeleton → Review Skeleton → **Identify People** → Enrich → Review Details → Generate
```

### Step-by-step flow

**Step 1: Detect & embed faces**
- Scan all trip photos using deepface (RetinaFace backend for accuracy)
- Extract face bounding boxes + 512-dim embeddings per face
- Store embeddings in session data (JSON-serializable as lists)
- Skip photos with no detected faces
- Estimated time: ~2.5 sec/photo on CPU, so 200 photos ≈ 8 minutes
  - Could parallelize with multiprocessing for speedup
  - Only needs to run once per trip (results cached in session)

**Step 2: Cluster faces**
- Run DBSCAN on all face embeddings (eps=0.6-1.0, min_samples=2)
- Group into person clusters: "Person 1 (47 photos)", "Person 2 (42 photos)", etc.
- Sort clusters by frequency (most-seen people first)
- Filter out noise cluster (strangers, partial faces, false positives)

**Step 3: User identifies people (interactive)**
- Show the user a representative face crop from each cluster (pick the best-quality detection)
- Ask them to name each person: "This person appears in 47 photos. Who is this?"
- Only prompt for top N clusters (e.g., people appearing in 5+ photos)
- Store name→cluster mapping in session data
- GUI: grid of face thumbnails with name input fields
- CLI: show face crops and prompt for names

**Step 4: Annotate photos with person names**
- For each photo, look up which face clusters are present
- Add person names to the Photo model (new field: `people: list[str]`)
- This data flows into the enrich step

**Step 5: Enrich with person context**
- When calling vision API for photo descriptions, include person names in the prompt context
- Example context: `"People in this photo: Matt, Karen"`
- Vision API can then generate: "Karen admiring the cherry blossoms while Matt takes a photo"
- The vision API doesn't need to identify faces — we've already told it who's there

## Model Changes

```python
# models.py — additions
@dataclass
class Face:
    photo_id: str          # which photo this face was found in
    bbox: tuple[int, int, int, int]  # x, y, w, h bounding box
    embedding: list[float] # 512-dim face embedding vector
    cluster_id: int        # assigned after clustering (-1 = noise)
    person_name: str       # assigned after user identification ("" if unnamed)

# Photo dataclass — new field
@dataclass
class Photo:
    ...
    people: list[str] = field(default_factory=list)  # named people in this photo
```

## New Files

| File | Purpose |
|------|---------|
| `src/post_trip_summary/pipeline/faces.py` | Face detection, embedding, clustering logic |
| `src/post_trip_summary/pipeline/review_people.py` | Interactive person naming (CLI) |
| `src/post_trip_summary/templates/people.html` | GUI page for naming face clusters |
| `tests/test_faces.py` | Unit tests for clustering logic |

## Dependencies

- `deepface>=0.0.93` — face detection + embedding
- `scikit-learn` — DBSCAN clustering (may already be a transitive dep)
- `tf-keras` or `tensorflow` — deepface backend (heavyweight, ~500MB)
  - **Alternative:** deepface with ONNX backend to avoid TensorFlow dependency — worth investigating

## Cost & Performance Considerations

- **No API costs** — all face processing runs locally
- **CPU time:** ~2.5 sec/photo, so a 300-photo trip ≈ 12 minutes for first run
  - Multiprocessing could cut this to ~3-4 minutes on a 4-core machine
  - Results cached in session — only runs once
- **Disk space:** Face embeddings for 300 photos ≈ ~1MB (negligible)
- **Dependency weight:** TensorFlow/Keras is heavy (~500MB). Investigate ONNX-only mode to keep install light

## Open Questions

1. **TensorFlow dependency weight** — deepface defaults to TF/Keras. Can we use the ONNX backend to avoid the ~500MB TensorFlow install? This matters for a hobby project.
2. **Face crop storage** — should we save face thumbnail crops to disk for the review UI, or generate them on the fly from the original photos + bounding boxes?
3. **Incremental updates** — if the user adds photos to a trip, do we re-run face detection on all photos or only new ones?
4. **Multiple trips** — should face identity carry across trips? ("Matt" in Trip A is the same "Matt" in Trip B.) This would require a global face database.
5. **Privacy** — face embeddings are biometric data. Should we encrypt them or add a setting to opt out?

## Verification (when implemented)

1. Unit test: DBSCAN clustering on synthetic embeddings produces expected groupings
2. Unit test: Person name annotation flows through to Photo model
3. Integration test: End-to-end on a small set of test photos with known faces
4. Manual test: Run on a real trip, verify face clusters make sense, verify personalized captions in output
