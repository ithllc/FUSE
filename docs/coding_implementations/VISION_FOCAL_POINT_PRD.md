# Product Requirements Document (PRD): Vision Focal Point Enhancement

**Feature Name**: Vision Focal Point Enhancement
**Parent Product**: FUSE (The Collaborative Brainstorming Intelligence)
**Target Module**: `src/vision/vision_state_capture.py`
**Status**: Draft
**Date**: 2026-03-11

---

## 1. Introduction

**Vision Focal Point Enhancement** adds intelligent scene understanding to FUSE's camera pipeline, replacing the current generic "extract all components" prompt with a two-pass vision system that classifies the scene, isolates the region of interest, and applies mode-specific extraction prompts. This addresses the core gap where FUSE's vision model processes the entire camera frame — person, hands, background, furniture — with no ability to focus on the relevant content (whiteboard, proxy objects, or gestures).

## 2. Problem Statement

The current `VisionStateCapture.process_received_frame()` sends raw camera frames to `gemini-3.1-flash-lite-preview` with a single hardcoded prompt:

> "Analyze this whiteboard image or technical sketch. Extract all technical nodes and relationships. Output ONLY valid Mermaid.js code."

**Issues:**
1. **No scene classification** — The model doesn't know if it's looking at a whiteboard, a person holding objects, or someone gesturing.
2. **No focal point isolation** — The entire frame is processed, including irrelevant background elements (walls, furniture, other people), which dilutes extraction accuracy.
3. **No mode awareness** — The same prompt is used regardless of whether the user is in Whiteboard, Charades, or Imagine mode.
4. **No context injection** — The proxy object registry (stored in Redis) is never fed to the vision model, so it cannot recognize that "the coffee cup is the database cluster."
5. **Charades mode is unimplemented** — No gesture recognition or spatial reasoning exists.

## 3. Target Audience

- **System Architects**: Need accurate whiteboard extraction without noise from surrounding environment.
- **Brainstorming Teams**: Need proxy object recognition during Imagine mode sessions where physical items represent architecture components.
- **Solo Prototypers**: Need gesture-based modeling (Charades) to work naturally without precise camera framing.

## 4. Scope & Constraints

- **Platform**: Google Cloud Run (FastAPI backend), Gemini Vision API
- **Model**: `gemini-3.1-flash-lite-preview` (location: `global`) — must stay within latency budget for real-time use
- **Licensing**: AGPL-3.0
- **Deployment**: Cloud-first (GCP), single-container on Cloud Run
- **Latency Budget**: Scene classification pass must complete in <500ms; total two-pass pipeline must complete in <1500ms
- **Security**: No PII in vision frames; frames are not persisted beyond the session

**Out of Scope:**
- Multi-camera support
- Video stream processing (remains frame-based at 2-5 FPS)
- Training or fine-tuning Gemini models
- Client-side image preprocessing (cropping, filtering)
- Gemini 2.5+ segmentation masks (future enhancement)

## 5. Key Features

### 5.1. Scene Classification Pass (Pass 1)
- A lightweight first call to the vision model that classifies what the camera is looking at.
- **Output**: Scene type (`whiteboard`, `objects`, `gesture`, `mixed`, `unclear`) and optional bounding box coordinates for the region of interest.
- **Prompt**: Focused on classification only — no Mermaid extraction. Asks: "What is the primary subject? Return the scene type and bounding box `[ymin, xmin, ymax, xmax]` (normalized 0-1000) of the focal region."
- **User Interaction**: Transparent — the user does not see or interact with this pass.
- **AI/Models**: `gemini-3.1-flash-lite-preview` with structured output (JSON response)

### 5.2. ROI Cropping
- If Pass 1 returns bounding box coordinates, crop the original frame to that region before Pass 2.
- **Mechanism**: Server-side crop using the bounding box coordinates descaled to actual image dimensions. Uses OpenCV (`cv2`) which is already a dependency.
- **Fallback**: If no bounding box is returned or confidence is low, Pass 2 processes the full frame with mode-specific prompts.

### 5.3. Mode-Specific Extraction Prompts (Pass 2)
- Replace the single generic prompt with three tailored prompts based on the active session mode and scene classification result.

#### 5.3.1. Whiteboard Mode Prompt
- **Trigger**: Scene classified as `whiteboard` or session mode is `whiteboard`
- **Prompt**: "Focus exclusively on the whiteboard or sketch surface. Ignore people, hands, and background. Extract all boxes, labels, arrows, and connections. Output ONLY valid Mermaid.js 'graph TD' code."
- **Enhancement**: Instructs model to describe spatial layout (left-to-right, top-to-bottom) to preserve the user's intended flow direction.

#### 5.3.2. Imagine Mode Prompt (Proxy Objects)
- **Trigger**: Scene classified as `objects` or session mode is `imagine`
- **Prompt**: Includes the proxy registry from Redis as context. Example: "The following objects have been assigned roles: {coffee cup → Database Cluster, stapler → GPU Array, pen → Message Queue}. Identify these objects in the frame, determine their spatial relationships, and output Mermaid.js code reflecting the architecture they represent."
- **Context Injection**: Reads proxy registry from `SessionStateManager.get_proxy_registry()` and embeds it in the prompt.

#### 5.3.3. Charades Mode Prompt (Gestures)
- **Trigger**: Scene classified as `gesture` or session mode is `charades`
- **Prompt**: "Analyze the person's hand gestures and body positioning. Describe the spatial shape being formed (ring, star, hierarchy, pipeline, etc.). Cross-reference with the current architecture state and recent voice transcript to determine which component or topology is being described. Output Mermaid.js code reflecting the interpreted gesture."
- **Context Injection**: Feeds current Mermaid state and recent transcript excerpt for cross-reference.

### 5.4. Context Injection Pipeline
- Before Pass 2, gather relevant session context from Redis:
  - **Proxy Registry**: Object → component mappings (for Imagine mode)
  - **Current Mermaid State**: The existing diagram (for incremental updates in all modes)
  - **Recent Transcript**: Last 3-5 voice exchanges (for Charades cross-referencing)
- Inject this context into the extraction prompt as structured preamble.

### 5.5. Session Mode Management
- Add a `vision_mode` field to session state: `auto`, `whiteboard`, `imagine`, `charades`
- Default: `auto` (uses Pass 1 scene classification to select the prompt)
- Allow explicit mode override via voice command ("switch to whiteboard mode") or UI toggle
- The Live API handler (`GeminiLiveStreamHandler`) should detect mode-switch voice commands and update Redis

### 5.6. Incremental Diagram Updates
- Pass 2 prompts include the current Mermaid state so the model can ADD to or MODIFY the existing diagram rather than regenerating from scratch each frame.
- Reduces diagram flickering and prevents loss of components that are no longer in frame.

## 6. User Stories

1. *As a system architect, I want FUSE to focus on just the whiteboard when I point my camera at it, so that people and furniture in the background don't corrupt the extracted diagram.*
2. *As a brainstorming team member, I want FUSE to recognize the coffee cup I assigned as "Database Cluster" when it sees it in the camera, so the proxy object system actually works visually.*
3. *As a solo prototyper, I want to use hand gestures to describe a ring topology, and have FUSE interpret my gesture in context of what I just said aloud.*
4. *As a session facilitator, I want to switch between whiteboard and imagine modes mid-session, so I can fluidly move between sketching and object manipulation.*
5. *As a user, I want the diagram to update incrementally rather than regenerating from scratch each frame, so I don't lose components that are temporarily off-camera.*
6. *As a user, I want FUSE to automatically detect whether I'm showing a whiteboard or holding objects, so I don't have to manually switch modes.*

## 7. Technical Requirements

- **Backend**: Python 3.11+ / FastAPI on Cloud Run (existing stack)
- **Vision Model**: `gemini-3.1-flash-lite-preview` (Vertex AI, location=`global`)
- **Image Processing**: OpenCV (`cv2`) for ROI cropping — already in `requirements.txt`
- **State Store**: Redis (Memorystore) for proxy registry, session mode, current Mermaid state
- **AI Response Format**: Pass 1 must return structured JSON (`scene_type`, `bounding_box`, `confidence`). Pass 2 returns raw Mermaid code (existing format).
- **Privacy**: Frames are processed in-memory only, never persisted to disk or cloud storage.
- **Accessibility**: Vision mode can be controlled via voice commands (no mouse/keyboard required).

## 8. Success Metrics

- **Extraction Accuracy**: Whiteboard diagrams with ≥3 components extracted correctly >80% of the time (vs. current baseline with background noise)
- **Proxy Object Recognition**: When proxy registry has ≥1 mapping and objects are visible, the correct component name appears in the Mermaid output >70% of the time
- **Latency**: Two-pass pipeline completes in <1500ms for 95th percentile frames
- **Scene Classification**: Correct scene type identified >85% of the time in auto mode
- **User Satisfaction**: Mode switching (auto, manual) works without session interruption

## 9. Dependencies & Risks

| Risk | Mitigation |
|------|------------|
| Two API calls per frame doubles latency | Pass 1 uses minimal prompt + structured output for speed; consider caching scene type across consecutive similar frames |
| Bounding box accuracy varies by scene complexity | Fallback to full-frame processing when confidence is low |
| Proxy objects may be ambiguous (two cups) | Prompt includes color/size hints from registry; voice context disambiguates |
| Charades gesture interpretation is inherently imprecise | Cross-reference with audio transcript; treat as "suggested" topology, confirm via voice |
| Model cost increase (~2x vision API calls) | Scene classification pass is lightweight; ROI cropping reduces Pass 2 token usage |

## 10. Implementation Phases

### Phase 1: Scene Classification + Whiteboard Focus
- Add Pass 1 scene classification with bounding box detection
- Add ROI cropping logic
- Replace generic prompt with whiteboard-specific prompt
- Add `vision_mode` to session state

### Phase 2: Imagine Mode + Context Injection
- Build context injection pipeline (proxy registry → prompt)
- Add Imagine mode prompt with object recognition
- Wire `SessionStateManager.get_proxy_registry()` into vision pipeline

### Phase 3: Charades Mode + Incremental Updates
- Add Charades mode prompt with gesture interpretation
- Add transcript cross-referencing
- Implement incremental diagram updates (current Mermaid state → prompt)

### Phase 4: Mode Switching + Polish
- Voice command mode switching via Live API handler
- UI mode toggle
- Frame-to-frame scene type caching to reduce redundant Pass 1 calls
- Latency optimization and testing

---

**Next Step**: Run `/technical-planner` to generate the implementation plan from this PRD.
