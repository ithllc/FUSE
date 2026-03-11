# Technical Implementation Plan: Vision Focal Point Enhancement

**PRD Reference**: `docs/coding_implementations/VISION_FOCAL_POINT_PRD.md`
**Date**: 2026-03-11
**Status**: Draft

---

## Overview

Replace the single-pass generic vision pipeline in `VisionStateCapture` with a two-pass, mode-aware system:

1. **Pass 1 (Scene Classification)**: Lightweight call to classify the scene and return bounding box ROI
2. **Pass 2 (Mode-Specific Extraction)**: Tailored prompt with ROI-cropped image and injected session context

The implementation touches 3 existing files and creates 2 new modules, organized into 4 sequential phases.

---

## Architecture

```
Camera Frame (JPEG bytes)
       │
       ▼
┌─────────────────────────┐
│  Pass 1: Scene Classify  │  ← gemini-3.1-flash-lite-preview
│  Returns: scene_type,    │     Structured JSON output
│  bounding_box, confidence│
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  ROI Crop (if bbox)      │  ← OpenCV cv2 (already in deps)
│  Descale 0-1000 → px    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Context Injection       │  ← Redis: proxy registry, mermaid
│  Build mode-specific     │     state, recent transcript
│  prompt with context     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Pass 2: Extract         │  ← gemini-3.1-flash-lite-preview
│  Mode: whiteboard |      │     Mode-specific prompt
│  imagine | charades      │
│  Returns: Mermaid code   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  State Update            │  ← Redis: merge into existing
│  Incremental merge       │     architectural_state
└─────────────────────────┘
```

---

## File Manifest (All Phases)

| Action | File | Purpose |
|--------|------|---------|
| **Modify** | `src/vision/vision_state_capture.py` | Rewrite `process_received_frame()` with two-pass pipeline |
| **Create** | `src/vision/scene_classifier.py` | Pass 1 logic: classify scene, extract bounding box |
| **Create** | `src/vision/vision_prompts.py` | Mode-specific prompt templates + context injection |
| **Modify** | `src/state/session_state_manager.py` | Add `get_proxy_registry()`, `get_vision_mode()`, `set_vision_mode()`, `get_recent_transcript()` |
| **Modify** | `src/audio/gemini_live_stream_handler.py` | Detect vision mode-switch voice commands |
| **Modify** | `main.py` | Expose `/vision/mode` endpoint, pass mode to frame handler |
| **Modify** | `static/index.html` | Add vision mode toggle in UI (Phase 4) |

---

## Phase 1: Scene Classification + Whiteboard Focus

### Objectives
- Add Pass 1 scene classification with bounding box detection
- Add ROI cropping using OpenCV
- Replace generic prompt with whiteboard-specific prompt
- Add `vision_mode` to Redis session state

### Implementation Steps

#### Step 1.1: Create `src/vision/scene_classifier.py`

New module with a `SceneClassifier` class:

```python
class SceneClassifier:
    """Pass 1: Classifies what the camera sees and returns ROI bounding box."""

    CLASSIFICATION_PROMPT = """Analyze this image and classify the primary subject.
Return ONLY a JSON object with these fields:
- "scene_type": one of "whiteboard", "objects", "gesture", "mixed", "unclear"
- "bounding_box": [ymin, xmin, ymax, xmax] normalized 0-1000 for the focal region, or null if unclear
- "confidence": float 0.0-1.0

Example: {"scene_type": "whiteboard", "bounding_box": [100, 50, 900, 950], "confidence": 0.92}"""

    def __init__(self, client, model_id):
        self.client = client
        self.model_id = model_id

    def classify(self, frame_bytes: bytes) -> dict:
        """Returns {"scene_type": str, "bounding_box": list|None, "confidence": float}"""
        # Call Gemini with CLASSIFICATION_PROMPT
        # Parse JSON response
        # Return with fallback defaults on parse failure
```

**Key decisions:**
- Reuses the same `gemini-3.1-flash-lite-preview` model and client instance (shared with Pass 2)
- JSON parsing with fallback: if response isn't valid JSON, return `{"scene_type": "unclear", "bounding_box": None, "confidence": 0.0}`
- Prompt explicitly instructs "Return ONLY a JSON object" — no markdown blocks

#### Step 1.2: Add ROI cropping utility to `scene_classifier.py`

```python
def crop_to_roi(frame_bytes: bytes, bounding_box: list, min_confidence: float = 0.6) -> bytes:
    """Crops JPEG frame to bounding box region. Returns original if crop fails."""
    # Decode JPEG → numpy array via cv2.imdecode
    # Descale bounding_box from 0-1000 to actual pixel dimensions
    # Crop: img[ymin:ymax, xmin:xmax]
    # Re-encode to JPEG bytes via cv2.imencode
    # Return original frame_bytes if any step fails
```

**Key decisions:**
- `min_confidence` threshold: below 0.6, skip cropping and use full frame
- OpenCV `cv2.imdecode` / `cv2.imencode` for JPEG ↔ numpy (already a dependency: `opencv-python-headless`)
- Bounding box format: `[ymin, xmin, ymax, xmax]` normalized 0-1000 (Gemini standard)
- Descale: `pixel_y = int(ymin * img_height / 1000)`

#### Step 1.3: Create `src/vision/vision_prompts.py`

Module containing prompt templates for each mode:

```python
WHITEBOARD_PROMPT = """Focus exclusively on the whiteboard or sketch surface in this image.
Ignore all people, hands, furniture, and background elements.
Extract all boxes, labels, arrows, and connections visible on the writing surface.
Preserve the spatial layout (left-to-right or top-to-bottom flow direction).
{context_block}
Output ONLY valid Mermaid.js 'graph TD' or 'graph LR' code. No markdown blocks or other text."""

IMAGINE_PROMPT = """The following physical objects have been assigned as architecture components:
{proxy_registry}

Identify these objects in the image. Determine their spatial relationships (proximity, grouping, pointing direction).
Map the physical arrangement to the architecture they represent.
{context_block}
Output ONLY valid Mermaid.js 'graph TD' code reflecting the architecture. No markdown blocks or other text."""

CHARADES_PROMPT = """Analyze the person's hand gestures and body positioning in this image.
Describe the spatial shape being formed (ring, star, hierarchy, pipeline, mesh, etc.).
Recent voice context: {transcript_excerpt}
{context_block}
Cross-reference the gesture with the voice context to determine which topology or component is being described.
Output ONLY valid Mermaid.js 'graph TD' code. No markdown blocks or other text."""

GENERIC_FALLBACK_PROMPT = """Analyze this image for any technical architecture content.
Extract all components and relationships visible.
{context_block}
Output ONLY valid Mermaid.js 'graph TD' code. No markdown blocks or other text."""

def build_context_block(current_mermaid: str = None) -> str:
    """Builds the incremental context block injected into all prompts."""
    if not current_mermaid:
        return ""
    return f"Current diagram state (update incrementally, do not regenerate from scratch):\n```\n{current_mermaid}\n```"
```

**Key decisions:**
- All prompts include a `{context_block}` placeholder for incremental diagram state
- `IMAGINE_PROMPT` has a `{proxy_registry}` placeholder populated from Redis
- `CHARADES_PROMPT` has a `{transcript_excerpt}` placeholder populated from recent events
- Fallback prompt exists for `mixed`/`unclear` scene classifications

#### Step 1.4: Add session state methods to `session_state_manager.py`

Add these methods to `SessionStateManager`:

```python
def get_proxy_registry(self) -> Dict[str, str]:
    """Returns full proxy registry as {object_id: technical_role} dict."""
    key = f"{self.session_id}:proxy_registry"
    return self.r.hgetall(key) or {}

def get_vision_mode(self) -> str:
    """Returns current vision mode: auto|whiteboard|imagine|charades. Default: auto."""
    key = f"{self.session_id}:vision_mode"
    return self.r.get(key) or "auto"

def set_vision_mode(self, mode: str):
    """Sets the vision mode."""
    key = f"{self.session_id}:vision_mode"
    self.r.set(key, mode)

def get_recent_transcript(self, limit: int = 5) -> str:
    """Returns last N transcript events as a single string for context injection."""
    events = self.get_events(limit=limit * 3)  # Over-fetch, filter to transcript
    transcript_events = [e for e in events if e.get("type") in ("voice_input", "proxy_assignment")]
    lines = []
    for e in transcript_events[:limit]:
        payload = e.get("payload", {})
        lines.append(payload.get("text", payload.get("role", str(payload))))
    return "\n".join(lines) if lines else ""
```

#### Step 1.5: Rewrite `vision_state_capture.py`

Replace `process_received_frame()` with the two-pass pipeline:

```python
from src.vision.scene_classifier import SceneClassifier, crop_to_roi
from src.vision.vision_prompts import (
    WHITEBOARD_PROMPT, IMAGINE_PROMPT, CHARADES_PROMPT,
    GENERIC_FALLBACK_PROMPT, build_context_block
)

class VisionStateCapture:
    def __init__(self, project_id, state_manager, location="global"):
        # ... existing init ...
        self.scene_classifier = SceneClassifier(self.client, self.model_id)

    def process_received_frame(self, frame_bytes: bytes) -> str:
        # 1. Determine vision mode
        vision_mode = self.state_manager.get_vision_mode()

        # 2. Pass 1: Scene classification (skip if mode is explicit)
        if vision_mode == "auto":
            classification = self.scene_classifier.classify(frame_bytes)
            scene_type = classification["scene_type"]
            bbox = classification.get("bounding_box")
            confidence = classification.get("confidence", 0.0)
        else:
            scene_type = vision_mode
            bbox = None
            confidence = 1.0

        # 3. ROI crop if bounding box available
        if bbox and confidence >= 0.6:
            cropped = crop_to_roi(frame_bytes, bbox)
        else:
            cropped = frame_bytes

        # 4. Build mode-specific prompt
        prompt = self._build_prompt(scene_type)

        # 5. Pass 2: Extract with mode-specific prompt
        mermaid_code = self._extract(cropped, prompt)

        # 6. Update state
        if mermaid_code:
            self.state_manager.update_architectural_state(mermaid_code)
            self.state_manager.log_event("vision_update", {
                "scene_type": scene_type,
                "confidence": confidence,
                "cropped": bbox is not None,
                "mermaid_length": len(mermaid_code)
            })

        return mermaid_code

    def _build_prompt(self, scene_type: str) -> str:
        context = build_context_block(self.state_manager.get_architectural_state())

        if scene_type == "whiteboard":
            return WHITEBOARD_PROMPT.format(context_block=context)
        elif scene_type == "objects" or scene_type == "imagine":
            registry = self.state_manager.get_proxy_registry()
            registry_str = "\n".join(f"- {obj} → {role}" for obj, role in registry.items()) or "No objects assigned yet."
            return IMAGINE_PROMPT.format(proxy_registry=registry_str, context_block=context)
        elif scene_type == "gesture" or scene_type == "charades":
            transcript = self.state_manager.get_recent_transcript(limit=5)
            return CHARADES_PROMPT.format(transcript_excerpt=transcript or "No recent voice context.", context_block=context)
        else:
            return GENERIC_FALLBACK_PROMPT.format(context_block=context)

    def _extract(self, frame_bytes: bytes, prompt: str) -> str:
        """Pass 2: Sends cropped frame + mode-specific prompt to Gemini."""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Content(role="user", parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg")
                    ])
                ]
            )
            return response.text.strip() if response.text else ""
        except Exception as e:
            print(f"Vision extraction error: {e}")
            return ""
```

### Dependencies
- None (this is the foundation phase)

### Testing
- Unit test `SceneClassifier` with sample images: whiteboard, person holding objects, person gesturing
- Unit test `crop_to_roi` with known bounding boxes
- Integration test: full `process_received_frame()` with `vision_mode="whiteboard"` vs `vision_mode="auto"`

---

## Phase 2: Imagine Mode + Context Injection

### Objectives
- Wire proxy registry from Redis into vision prompts
- Test Imagine mode with physical objects
- Add `/vision/mode` API endpoint

### Implementation Steps

#### Step 2.1: Add vision mode endpoint to `main.py`

```python
@app.get("/vision/mode")
async def get_vision_mode():
    """Returns the current vision processing mode."""
    if not state_manager:
        return {"status": "error", "message": "State manager not initialized."}
    return {"status": "ok", "mode": state_manager.get_vision_mode()}

@app.post("/vision/mode")
async def set_vision_mode(request: Request):
    """Sets the vision processing mode: auto|whiteboard|imagine|charades."""
    if not state_manager:
        return {"status": "error", "message": "State manager not initialized."}
    body = await request.json()
    mode = body.get("mode", "auto")
    if mode not in ("auto", "whiteboard", "imagine", "charades"):
        return {"status": "error", "message": f"Invalid mode: {mode}"}
    state_manager.set_vision_mode(mode)
    return {"status": "ok", "mode": mode}
```

#### Step 2.2: Pass session mode to `/vision/frame`

Update the `/vision/frame` endpoint to accept an optional `mode` query parameter override:

```python
@app.post("/vision/frame")
async def receive_frame(request: Request, mode: Optional[str] = None):
    """Receives a binary image frame. Optional ?mode=whiteboard|imagine|charades override."""
    # ... existing validation ...
    if mode and mode in ("whiteboard", "imagine", "charades"):
        state_manager.set_vision_mode(mode)
    mermaid_code = vision_capture.process_received_frame(frame_bytes)
    return {"status": "success", "mermaid_length": len(mermaid_code)}
```

#### Step 2.3: Verify proxy registry integration

The proxy registry is already populated by `GeminiLiveStreamHandler.process_simulated_command()` when users say "This X is our Y". Phase 1's `_build_prompt()` already reads it via `state_manager.get_proxy_registry()`. This step verifies end-to-end:

1. User says "This coffee cup is our database" → proxy stored in Redis
2. User points camera at coffee cup → Pass 1 classifies as `objects`
3. Pass 2 prompt includes "coffee cup → database" from registry
4. Mermaid output references "Database" component

### Dependencies
- Phase 1 complete

### Testing
- End-to-end: Set proxy via `/command`, then submit frame via `/vision/frame`, verify Mermaid output references proxy role
- Test mode override: `/vision/frame?mode=imagine` forces Imagine prompt regardless of scene content

---

## Phase 3: Charades Mode + Incremental Updates

### Objectives
- Enable gesture interpretation with voice cross-referencing
- Add transcript logging for context injection
- Implement incremental diagram updates

### Implementation Steps

#### Step 3.1: Add voice transcript logging

In `main.py`'s `send_to_client()` function (inside the WebSocket handler), log text responses as transcript events:

```python
if hasattr(part, 'text') and part.text:
    await websocket.send_text(json.dumps({"text": part.text}))
    # Log for vision context injection
    state_manager.log_event("voice_input", {"text": part.text})
```

Similarly, log user text messages in `receive_from_client()`:

```python
elif "text" in message:
    # ... existing parsing ...
    state_manager.log_event("voice_input", {"text": text_val})
    await session.send(input=text_val, end_of_turn=True)
```

#### Step 3.2: Test Charades mode end-to-end

1. User says "I'm going to show you a ring topology" → logged as transcript event
2. User makes a circular gesture with hands → camera captures frame
3. Pass 1: scene classified as `gesture`
4. Pass 2: Charades prompt includes "I'm going to show you a ring topology" as transcript context
5. Model interprets the circular gesture + voice context → outputs ring topology Mermaid code

#### Step 3.3: Incremental diagram updates

Already designed into Phase 1's `build_context_block()` — the current Mermaid state is injected into every Pass 2 prompt with the instruction "update incrementally, do not regenerate from scratch."

Additional refinement: add a merge-vs-replace heuristic:

```python
def _should_merge(self, new_mermaid: str, existing_mermaid: str) -> str:
    """Simple heuristic: if new output has fewer nodes than existing, merge. Otherwise replace."""
    new_nodes = len([l for l in new_mermaid.split('\n') if '-->' in l or '---' in l])
    existing_nodes = len([l for l in existing_mermaid.split('\n') if '-->' in l or '---' in l])

    if new_nodes < existing_nodes * 0.5:
        # New output is much smaller — likely partial view, keep existing
        return existing_mermaid
    return new_mermaid
```

**Note**: This is a basic heuristic. A more sophisticated merge (AST-level Mermaid diffing) is out of scope for this phase but flagged as a future improvement.

### Dependencies
- Phase 1 and Phase 2 complete
- Voice transcript logging (Step 3.1) must be in place before Charades works

### Testing
- Verify transcript events appear in Redis event log
- Verify `get_recent_transcript()` returns the last N voice entries
- End-to-end Charades test with gesture + voice context

---

## Phase 4: Mode Switching + UI + Polish

### Objectives
- Voice-activated mode switching via Live API
- UI mode selector toggle
- Frame-to-frame scene caching to reduce redundant Pass 1 calls
- Latency optimization

### Implementation Steps

#### Step 4.1: Voice command mode switching

Update `GeminiLiveStreamHandler.process_simulated_command()` to detect mode-switch phrases:

```python
MODE_KEYWORDS = {
    "whiteboard mode": "whiteboard",
    "sketch mode": "whiteboard",
    "imagine mode": "imagine",
    "object mode": "imagine",
    "proxy mode": "imagine",
    "charades mode": "charades",
    "gesture mode": "charades",
    "auto mode": "auto",
}

async def process_simulated_command(self, text: str):
    text_lower = text.lower()

    # Check for mode switch commands
    for phrase, mode in MODE_KEYWORDS.items():
        if phrase in text_lower:
            self.state_manager.set_vision_mode(mode)
            self.state_manager.log_event("mode_switch", {"mode": mode})
            return f"Switched to {mode} mode."

    # ... existing proxy assignment logic ...
```

**Note**: In the current WebSocket flow, voice commands are streamed as raw audio to Gemini Live, not parsed server-side. The mode-switch detection would need to happen either:
- (a) In the Gemini system instruction (tell the model to output a special token like `[MODE:whiteboard]` when it hears a mode switch), or
- (b) Via the existing `/command` text endpoint for typed commands

For Phase 4, implement option (b) first (simpler), and document option (a) as a future enhancement when Gemini function calling is available in Live API.

#### Step 4.2: UI mode toggle

Add a mode selector to `static/index.html` in the Live Camera Feed panel:

```html
<div class="vision-mode-selector">
    <label>Vision Mode:</label>
    <select id="visionMode" onchange="setVisionMode(this.value)">
        <option value="auto" selected>Auto Detect</option>
        <option value="whiteboard">Whiteboard</option>
        <option value="imagine">Imagine (Objects)</option>
        <option value="charades">Charades (Gestures)</option>
    </select>
</div>
```

```javascript
async function setVisionMode(mode) {
    const resp = await fetch('/vision/mode', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({mode})
    });
    const data = await resp.json();
    if (data.status === 'ok') showToast(`Vision mode: ${mode}`);
}
```

#### Step 4.3: Scene classification caching

Add a simple cache to `VisionStateCapture` to skip Pass 1 when consecutive frames have the same scene type:

```python
class VisionStateCapture:
    def __init__(self, ...):
        # ... existing init ...
        self._cached_scene = None
        self._cache_hits = 0
        self._cache_max = 5  # Re-classify after 5 consecutive cache hits

    def process_received_frame(self, frame_bytes):
        vision_mode = self.state_manager.get_vision_mode()

        if vision_mode == "auto":
            if self._cached_scene and self._cache_hits < self._cache_max:
                scene_type = self._cached_scene["scene_type"]
                bbox = self._cached_scene.get("bounding_box")
                confidence = self._cached_scene.get("confidence", 0.0)
                self._cache_hits += 1
            else:
                classification = self.scene_classifier.classify(frame_bytes)
                scene_type = classification["scene_type"]
                bbox = classification.get("bounding_box")
                confidence = classification.get("confidence", 0.0)
                self._cached_scene = classification
                self._cache_hits = 0
        # ... rest of pipeline ...
```

This reduces Pass 1 calls by ~80% (1 call per 5 frames instead of every frame), saving ~400ms per cached frame.

#### Step 4.4: Latency optimization

- **Async Pass 1**: Convert `SceneClassifier.classify()` to async (`generate_content_async`)
- **Timeout**: Add 2-second timeout on each Gemini call to prevent frame processing backlog
- **Skip frames**: If a frame arrives while a previous frame is still processing, drop the new frame (debounce at the `/vision/frame` endpoint level)

```python
# In main.py
_processing_frame = False

@app.post("/vision/frame")
async def receive_frame(request: Request, mode: Optional[str] = None):
    global _processing_frame
    if _processing_frame:
        return {"status": "skipped", "reason": "Previous frame still processing"}
    _processing_frame = True
    try:
        # ... process frame ...
    finally:
        _processing_frame = False
```

### Dependencies
- Phases 1-3 complete

### Testing
- Voice command mode switching via `/command` endpoint
- UI mode toggle updates Redis and affects next frame processing
- Cache hit/miss ratio with continuous frame stream
- Latency benchmarks: measure P50/P95 for single-pass (cached) vs two-pass pipeline

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pass 1 JSON parsing fails (model returns prose) | Medium | Low | Robust fallback: treat as `unclear`, use full frame + generic prompt |
| Bounding box crops out relevant content | Low | Medium | Confidence threshold (0.6); below threshold → use full frame |
| Two-pass latency exceeds 1500ms budget | Medium | Medium | Scene caching reduces to single-pass 80% of the time; async calls |
| Proxy objects visually ambiguous | Medium | Medium | Prompt includes color/size hints; voice context disambiguates |
| Charades gesture misinterpretation | High | Low | Cross-reference with transcript; treat as suggestion, not authoritative |
| Increased Gemini API costs (~2x calls) | Low | Low | Scene caching reduces actual calls; ROI cropping reduces token usage |

---

## Success Criteria

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Whiteboard extraction accuracy | >80% with ≥3 components | Manual test with 10 sample whiteboard images |
| Proxy object recognition | >70% when registry has ≥1 mapping | End-to-end test with known proxy assignments |
| Two-pass latency (P95) | <1500ms | Log timestamps in `process_received_frame()` |
| Scene classification accuracy | >85% correct in auto mode | Manual test with 20 mixed-scene images |
| Zero regressions | No degradation in existing whiteboard-only mode | Compare before/after with same test images |

---

## Dependency Graph

```
Phase 1 ──────────────────► Phase 2 ──────────────────► Phase 3 ──────────────────► Phase 4
(Scene Classify +           (Imagine + Context           (Charades + Incremental     (Voice Switch +
 Whiteboard Focus)           Injection + API)             + Transcript Logging)       UI + Cache + Perf)
                                    │                            │
                                    │                            │
                            Blocked by:                  Blocked by:
                            - Phase 1 complete           - Phase 2 complete
                            - Proxy registry exists      - Transcript logging
                              (already in Redis)           (Step 3.1)
```

All phases are sequential. No parallelization is possible because each phase builds on the infrastructure from the previous phase.

---

**Next Step**: Run `/project` to ingest this plan into the kanban board, or begin implementation starting with Phase 1.
