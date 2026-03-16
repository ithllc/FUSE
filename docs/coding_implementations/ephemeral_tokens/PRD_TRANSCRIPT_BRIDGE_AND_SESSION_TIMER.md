# PRD: Transcript Context Bridge + Brainstorming Session Timer

**Issue**: #39
**Status**: Draft
**Author**: FUSE Team
**Date**: 2026-03-16
**Priority**: P0 — Critical Path (diagram quality + user experience)
**Related Issues**: #32 (Mermaid Render Error), #34 (Generation unrelated to user description)

---

## 1. Problem Statement

The ephemeral tokens solution (`static/index_ephemeral_tokens.html`) has a critical architectural gap: the browser connects directly to Gemini for audio, but **never relays transcript text back to the server**. This means the server-side vision pipeline — which generates Mermaid architecture diagrams — operates without any knowledge of what the user has been saying.

### 1.1 Missing Transcript Context

In the **server-to-server** solution, the server proxies all audio and stores transcripts in Redis via `state_manager.log_event("transcript", ...)`. When the vision pipeline runs Pass 2 (mode-specific extraction), it calls `state_manager.get_recent_transcript(limit=5)` to inject conversational context into prompts. The diagram is built from **what the user sees + what the user says**.

In the **ephemeral tokens** solution:
- Transcripts are displayed in the browser UI but never sent to the server
- `get_recent_transcript()` always returns empty/null on the server
- **Charades mode** receives `"No recent voice context."` — completely blind to conversation
- **Imagine mode** has no conversational nuance for object-role mapping
- Diagrams are built purely from camera frames, divorced from user intent

The issue #32 fix (removing `checkForMermaid()` from conversational text) compounded this by eliminating the last path through which conversation could influence the diagram.

**This is the root cause of issue #34 ("Generation had nothing to do with what I mentioned") — the pipeline literally cannot hear what the user is saying.**

### 1.2 No Brainstorming Phase Boundary

There is no mechanism to tell the user when to stop describing their idea:
- Each new vision frame may partially overwrite the diagram mid-thought
- The 3-second auto-workflow debounce triggers on incomplete diagrams
- The workflow can fire multiple times on intermediate states, wasting Imagen/Veo3 API calls
- Users have no feedback on how much capture time remains
- Extended sessions cause **context rot** — earlier coherent ideas get degraded by later frames

### 1.3 No Backend Observability

When diagram generation fails or produces unexpected results, there is no structured logging to diagnose which pipeline stage failed (classification, extraction, merge, validation, visualization, animation). The only logging is `print()` statements that don't reach GCP Cloud Logging in a structured way.

---

## 2. Solution

Three coordinated changes:

### 2.1 Transcript Bridge
Add a `POST /api/transcript` endpoint. The browser sends transcript text to the server after each flush. The server stores it in Redis via the existing `SessionStateManager`. The vision pipeline now has full conversational context — matching server-to-server quality.

### 2.2 Brainstorming Session Timer (2:15)
A visible countdown timer embedded in the UI. At 15 seconds remaining, warn the user visually and audibly. At 0:00, gate the `capture_and_analyze_frame` tool (return "brainstorming complete" instead of capturing a new frame), then trigger `runAutoWorkflow()` exactly once on the final stable diagram.

### 2.3 Vision Pipeline Observability
Structured GCP Cloud Logging for each pipeline function execution (classification, extraction, merge) using Python's `logging` module with structured key=value format — consistent with existing `EVENT=` logging patterns in `main.py`. Not noisy: one log line per pipeline stage per frame, plus summary.

---

## 3. User Stories

| ID | Story | Acceptance Criteria |
|----|-------|-------------------|
| US-1 | As a FUSE user, I want my verbal descriptions to influence the architecture diagram | Vision pipeline receives transcript context; Charades mode prompt includes recent conversation |
| US-2 | As a FUSE user, I want to know how much time I have left to describe my idea | Visible countdown timer (2:15) appears in the UI during active session |
| US-3 | As a FUSE user, I want a warning before my brainstorming time expires | Visual warning indicator at 15 seconds remaining |
| US-4 | As a FUSE user, I want the system to process my complete idea, not a partial one | Auto-workflow triggers exactly once after brainstorming timer expires, not on intermediate states |
| US-5 | As a developer, I want to see which vision pipeline stage failed when diagrams are wrong | Structured Cloud Logging shows classification → extraction → merge → workflow stages with latency |
| US-6 | As a FUSE user, I want Gemini to still be active after brainstorming ends | Gemini session stays alive; only vision capture is gated — user can still converse |

---

## 4. Technical Architecture

### 4.1 Transcript Bridge

#### 4.1.1 Server: New Endpoint

**File**: `main.py`

```python
@app.post("/api/transcript")
async def receive_transcript(request: Request):
    """Receives transcript text from ephemeral token page for Redis storage.
    Bridges the gap between browser-side Gemini audio and server-side vision pipeline."""
```

- Accepts `{role: "user"|"fuse", text: "..."}` JSON payload
- Validates payload size (max 4KB) and role values
- Stores via `state_manager.log_event("transcript", {"role": role, "text": text})`
- Returns `{status: "ok"}`

#### 4.1.2 Client: Transcript Relay

**File**: `static/index_ephemeral_tokens.html`

After `flushTranscript(role)` assembles `fullText`, add a non-blocking `fetch()` to `POST /api/transcript`:

```javascript
function flushTranscript(role) {
    // ... existing logic ...
    // NEW: relay to server for vision pipeline context
    fetch(BASE + '/api/transcript', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({role: msgType === 'user' ? 'user' : 'fuse', text: fullText}),
        keepalive: true
    }).catch(() => {}); // fire-and-forget, don't block UI
}
```

#### 4.1.3 Server: State Manager

**File**: `src/state/session_state_manager.py`

Verify `get_recent_transcript(limit=N)` correctly retrieves transcript events from Redis. This method already exists and is used by the server-to-server vision pipeline — the transcript bridge ensures it has data to return in the ephemeral flow.

### 4.2 Brainstorming Session Timer

#### 4.2.1 Client: Timer Logic

**File**: `static/index_ephemeral_tokens.html`

```
Constants:
  BRAINSTORM_DURATION_MS = 135000  (2 minutes 15 seconds)
  BRAINSTORM_WARN_MS     = 120000  (warning at 2 minutes = 15 seconds remaining)

State:
  brainstormingComplete = false
  brainstormTimer = null
  brainstormWarningTimer = null
```

**Timer starts**: When the Gemini session connects and audio begins (same trigger as existing `sessionTimer`).

**At 2:00 (15s remaining)**:
- Show warning text in UI (e.g., "15 seconds remaining to describe your idea")
- Visual indicator (pulsing border or color change on timer element)

**At 2:15 (0:00)**:
- Set `brainstormingComplete = true`
- Update timer display to "Brainstorming Complete — Processing..."
- Clear any pending `autoWorkflowDebounce`
- Trigger `runAutoWorkflow()` immediately (no debounce)

#### 4.2.2 Client: Tool Call Gate

When `brainstormingComplete === true` and Gemini calls `capture_and_analyze_frame`:

```javascript
if (brainstormingComplete) {
    result = {
        status: 'brainstorming_complete',
        description: 'Brainstorming phase has ended. Processing the captured architecture.'
    };
    // Skip vision frame capture, skip refreshMermaid, skip debounce
}
```

The Gemini session is NOT terminated — the user can still converse. Only new vision capture is gated.

#### 4.2.3 UI: Timer Display

Embedded countdown timer visible in the session header area. Displays `MM:SS` remaining. Color transitions:
- Green (> 15s remaining)
- Yellow/pulsing (≤ 15s remaining — warning state)
- Completed state indicator after expiry

### 4.3 Vision Pipeline Observability

#### 4.3.1 Server: Structured Logging

**File**: `src/vision/vision_state_capture.py`

Replace `print()` statements with structured `logging` calls using the existing logger pattern from `main.py`:

```python
import logging
logger = logging.getLogger("fuse.vision")
```

Log points (one line per stage):
1. **Frame received**: `EVENT=vision_frame_received | mode={mode} | frame_size={len(frame_bytes)}`
2. **Classification**: `EVENT=vision_classification | scene_type={type} | confidence={conf} | cached={bool} | latency_ms={ms}`
3. **Extraction**: `EVENT=vision_extraction | mermaid_length={len} | latency_ms={ms}`
4. **Merge decision**: `EVENT=vision_merge | action={replace|keep_existing} | new_edges={n} | existing_edges={n}`
5. **Pipeline complete**: `EVENT=vision_pipeline_complete | total_latency_ms={ms} | scene_type={type} | mermaid_length={len}`

Error logging:
- `EVENT=vision_extraction_error | error={str(e)}`

This follows the same `EVENT=` structured format used by the existing `/api/session-event` and `/api/tool-event` handlers, ensuring consistent Cloud Logging parsing.

---

## 5. Scope

### 5.1 In Scope
- Transcript bridge endpoint and client relay
- Brainstorming countdown timer (2:15 with 15s warning)
- Tool call gating after timer expiry
- Structured vision pipeline logging
- All changes to ephemeral tokens solution only

### 5.2 Out of Scope
- Changes to server-to-server solution (`static/index.html`)
- Changes to Gemini system instructions or tool definitions
- Authentication or rate limiting on new endpoint
- Transcript aggregation via Gemini Flash-Lite (server-to-server does this; ephemeral keeps it simple with raw transcript relay)
- Persistent transcript storage beyond Redis session TTL

---

## 6. Technical Constraints

| Constraint | Detail |
|-----------|--------|
| **Redis dependency** | Transcript storage uses existing Redis session keys; no new infrastructure |
| **Payload size** | `/api/transcript` max 4KB per request (speech fragments are small) |
| **Timer accuracy** | Client-side `setTimeout`/`setInterval` — sufficient for ±100ms accuracy on 2:15 timer |
| **Logging volume** | ~5 log lines per vision frame × ~1 frame per tool call = low noise |
| **No breaking changes** | Server-to-server solution must continue working unchanged |

---

## 7. Success Metrics

| Metric | Target |
|--------|--------|
| Transcript available in Redis during ephemeral session | 100% of flush events stored |
| Vision pipeline receives non-empty transcript context | Charades/Imagine modes get real conversation text |
| Auto-workflow fires exactly once per session | After brainstorming timer expires, not on intermediate frames |
| Diagram relevance to user description | Qualitative: diagrams reflect what user said (validates #34 fix) |
| Cloud Logging visibility | All 5 pipeline stages visible in GCP Logs Explorer |

---

## 8. Handoff

- Run `/technical-plan` to generate the implementation plan from this PRD
- Run `/project` to manage implementation tasks
