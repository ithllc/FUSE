# Technical Implementation Plan: Transcript Bridge + Brainstorming Timer (Issue #39)

**PRD**: `PRD_TRANSCRIPT_BRIDGE_AND_SESSION_TIMER.md`
**Date**: 2026-03-16
**Files Modified**: 4

---

## Overview

Three work streams executed in dependency order. Phase 1 (Transcript Bridge) unblocks Phase 2 (Timer) since the timer's "gate close" depends on transcripts already being stored. Phase 3 (Observability) is independent and can be done in parallel.

## Architecture

```
Browser (ephemeral tokens page)
  │
  ├─ flushTranscript() ──POST /api/transcript──► main.py ──► Redis (transcript events)
  │                                                              │
  ├─ capture_and_analyze_frame ──POST /vision/frame──► vision_state_capture.py
  │       (gated by brainstormingComplete)                  │
  │                                                         ├─ get_recent_transcript() ← Redis ✓ (now has data)
  │                                                         ├─ classify → extract → merge
  │                                                         └─ structured logging → Cloud Logging
  │
  └─ brainstorming timer (2:15)
        ├─ 15s warning
        └─ expiry → gate tool + trigger runAutoWorkflow()
```

---

## Phase 1: Transcript Bridge

### Objective
Bridge browser-side transcripts to server-side Redis so the vision pipeline has conversational context.

### Bug Fix (Critical)
`SessionStateManager.get_recent_transcript()` filters for event types `"voice_input"` and `"proxy_assignment"`, but transcripts are logged as type `"transcript"` (main.py:338). This means transcript retrieval returns empty even in server-to-server. **Must fix the filter to include `"transcript"`.**

### Implementation Steps

#### Step 1.1: Fix `get_recent_transcript()` filter (session_state_manager.py:77)

**File**: `src/state/session_state_manager.py`
**Line**: 77

Change:
```python
transcript_events = [e for e in events if e.get("type") in ("voice_input", "proxy_assignment")]
```
To:
```python
transcript_events = [e for e in events if e.get("type") in ("transcript", "voice_input", "proxy_assignment")]
```

Also fix the text extraction (line 81) to handle the `"transcript"` payload shape `{"role": "user", "text": "..."}`:
```python
for e in transcript_events[:limit]:
    payload = e.get("payload", {})
    role = payload.get("role", "")
    text = payload.get("text", str(payload))
    prefix = f"[{role}] " if role else ""
    lines.append(f"{prefix}{text}")
```

#### Step 1.2: Add `POST /api/transcript` endpoint (main.py)

**File**: `main.py`
**Insert after**: Line ~1157 (after `/api/session-event` handler)

```python
# --- Transcript Bridge (Issue #39) ---
_VALID_TRANSCRIPT_ROLES = {"user", "fuse"}

@app.post("/api/transcript")
async def receive_transcript(request: Request):
    """Receives transcript text from ephemeral token page for Redis storage.
    Bridges browser-side Gemini audio transcripts to server-side vision pipeline context."""
    try:
        body = await request.body()
        if len(body) > 4096:
            return {"status": "error", "message": "Payload too large (max 4KB)"}

        data = json.loads(body)
        role = data.get("role", "")
        text = data.get("text", "").strip()

        if role not in _VALID_TRANSCRIPT_ROLES:
            return {"status": "error", "message": f"Invalid role: {role}"}
        if not text:
            return {"status": "error", "message": "Empty transcript text"}

        if state_manager:
            try:
                state_manager.log_event("transcript", {"role": role, "text": text})
            except Exception as e:
                logger.warning(f"EVENT=transcript_bridge_error | error={e}")

        logger.info(f"EVENT=transcript_bridge | role={role} | length={len(text)}")
        return {"status": "ok"}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}
    except Exception as e:
        logger.warning(f"EVENT=transcript_bridge_error | error={e}")
        return {"status": "error", "message": str(e)}
```

#### Step 1.3: Add client-side transcript relay (index_ephemeral_tokens.html)

**File**: `static/index_ephemeral_tokens.html`
**Function**: `flushTranscript(role)` (line ~1035-1043)

After `addMsg(msgType, fullText);` (line 1042), add:
```javascript
// Relay transcript to server for vision pipeline context (issue #39)
fetch(BASE + '/api/transcript', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({role: role, text: fullText}),
    keepalive: true
}).catch(() => {}); // fire-and-forget
```

### Dependencies
- None (this is the foundation)

### Files
| File | Change |
|------|--------|
| `src/state/session_state_manager.py` | Fix `get_recent_transcript()` filter + text extraction |
| `main.py` | Add `POST /api/transcript` endpoint |
| `static/index_ephemeral_tokens.html` | Add fetch relay in `flushTranscript()` |

---

## Phase 2: Brainstorming Session Timer

### Objective
Add a 2:15 countdown timer that gates vision capture input and triggers a single auto-workflow run.

### Implementation Steps

#### Step 2.1: Add timer constants and state (index_ephemeral_tokens.html)

**File**: `static/index_ephemeral_tokens.html`
**Insert after**: Session timeout constants (line ~1048)

```javascript
// --- Brainstorming timer (issue #39) ---
const BRAINSTORM_DURATION_MS = 135000; // 2 minutes 15 seconds
const BRAINSTORM_WARN_MS = 120000;     // warn at 2:00 (15s remaining)
let brainstormingComplete = false;
let brainstormTimer = null;
let brainstormWarnTimer = null;
let brainstormCountdown = null;
```

#### Step 2.2: Add timer UI element (index_ephemeral_tokens.html)

**File**: `static/index_ephemeral_tokens.html`
**Insert in header** (after status badge, ~line 696, before `</div>` closing btn-group):

```html
<div id="brainstormTimer" class="brainstorm-timer" style="display:none;">
    <span id="brainstormTimeLeft">2:15</span>
</div>
```

**CSS** (add to existing styles):
```css
.brainstorm-timer {
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
    padding: 4px 10px;
    border-radius: 6px;
    background: #238636;
    color: #ffffff;
    font-weight: 600;
    min-width: 50px;
    text-align: center;
}
.brainstorm-timer.warning {
    background: #d29922;
    animation: pulse-warn 1s ease-in-out infinite;
}
.brainstorm-timer.complete {
    background: #388bfd;
    font-size: 12px;
}
@keyframes pulse-warn {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
}
```

#### Step 2.3: Add timer start/stop/update functions (index_ephemeral_tokens.html)

**Insert after** timer constants:

```javascript
function startBrainstormTimer() {
    brainstormingComplete = false;
    const timerEl = document.getElementById('brainstormTimer');
    const timeEl = document.getElementById('brainstormTimeLeft');
    timerEl.style.display = '';
    timerEl.className = 'brainstorm-timer';

    let remaining = BRAINSTORM_DURATION_MS;

    // Update display every second
    function updateDisplay() {
        const secs = Math.ceil(remaining / 1000);
        const m = Math.floor(secs / 60);
        const s = secs % 60;
        timeEl.textContent = m + ':' + String(s).padStart(2, '0');
    }
    updateDisplay();

    brainstormCountdown = setInterval(() => {
        remaining -= 1000;
        if (remaining <= 0) remaining = 0;
        updateDisplay();
        if (remaining <= 0) {
            clearInterval(brainstormCountdown);
            brainstormCountdown = null;
            onBrainstormingComplete();
        }
    }, 1000);

    // Warning at 15 seconds remaining
    brainstormWarnTimer = setTimeout(() => {
        timerEl.classList.add('warning');
        addMsg('system', '15 seconds remaining to describe your idea.');
        addConnectionLog('BRAINSTORM: 15s warning', 'error');
    }, BRAINSTORM_WARN_MS);
}

function onBrainstormingComplete() {
    brainstormingComplete = true;
    const timerEl = document.getElementById('brainstormTimer');
    timerEl.className = 'brainstorm-timer complete';
    document.getElementById('brainstormTimeLeft').textContent = 'Processing...';
    addMsg('system', 'Brainstorming phase complete. Processing your architecture...');
    addConnectionLog('BRAINSTORM: Timer expired — gating vision input, triggering workflow', 'ok');

    // Clear any pending auto-workflow debounce and trigger immediately
    if (autoWorkflowDebounce) clearTimeout(autoWorkflowDebounce);
    autoWorkflowDebounce = null;

    // Trigger final auto-workflow if we have a valid diagram
    if (diagramValid) {
        runAutoWorkflow();
    } else {
        addConnectionLog('BRAINSTORM: No valid diagram to process', 'error');
        document.getElementById('brainstormTimeLeft').textContent = 'Complete';
    }
}

function clearBrainstormTimer() {
    if (brainstormTimer) { clearTimeout(brainstormTimer); brainstormTimer = null; }
    if (brainstormWarnTimer) { clearTimeout(brainstormWarnTimer); brainstormWarnTimer = null; }
    if (brainstormCountdown) { clearInterval(brainstormCountdown); brainstormCountdown = null; }
    brainstormingComplete = false;
}
```

#### Step 2.4: Hook timer into session lifecycle (index_ephemeral_tokens.html)

**Start timer**: In the session activation block (line ~1331, right after `startSessionTimer();`):
```javascript
startBrainstormTimer(); // issue #39
```

**Clear timer**: In `endSession()` / `clearSessionTimer()` and WebSocket close handler:
```javascript
clearBrainstormTimer(); // issue #39
```

#### Step 2.5: Gate `capture_and_analyze_frame` tool call (index_ephemeral_tokens.html)

**File**: `static/index_ephemeral_tokens.html`
**Location**: Inside the `capture_and_analyze_frame` handler (line ~1435)

Add gate check as the first thing inside the `if (funcName === 'capture_and_analyze_frame')` block:
```javascript
if (brainstormingComplete) {
    result = {
        status: 'brainstorming_complete',
        description: 'Brainstorming phase has ended (2:15 timer expired). Processing the captured architecture.'
    };
    addMsg('system', 'TOOL: Vision capture skipped — brainstorming phase complete.');
} else {
    // ... existing capture logic ...
}
```

#### Step 2.6: Suppress auto-workflow debounce during brainstorming complete (index_ephemeral_tokens.html)

In the `capture_and_analyze_frame` success path (line ~1465), wrap the debounce trigger:
```javascript
// Only debounce auto-workflow if brainstorming is still active
if (!brainstormingComplete) {
    if (autoWorkflowDebounce) clearTimeout(autoWorkflowDebounce);
    autoWorkflowDebounce = setTimeout(() => {
        if (sessionState === 'active' && diagramValid) runAutoWorkflow();
    }, 3000);
}
```

### Dependencies
- Phase 1 (transcripts must be flowing to Redis before timer expires and workflow runs)

### Files
| File | Change |
|------|--------|
| `static/index_ephemeral_tokens.html` | Timer UI, constants, lifecycle hooks, tool call gate |

---

## Phase 3: Vision Pipeline Observability

### Objective
Replace `print()` with structured logging in the vision pipeline for GCP Cloud Logging visibility.

### Implementation Steps

#### Step 3.1: Add structured logger (vision_state_capture.py)

**File**: `src/vision/vision_state_capture.py`
**Add at top** (after imports):

```python
import logging
logger = logging.getLogger("fuse.vision")
```

#### Step 3.2: Add logging to `process_received_frame()` (vision_state_capture.py)

Instrument each stage:

1. **After mode determination** (line ~101):
```python
logger.info(f"EVENT=vision_frame_received | mode={vision_mode} | frame_size={len(frame_bytes)}")
```

2. **After classification** (line ~116):
```python
logger.info(
    f"EVENT=vision_classification | scene_type={scene_type}"
    f" | confidence={confidence:.2f} | cached={self._cache_hits > 0}"
    f" | latency_ms={int((time.time() - t_start) * 1000)}"
)
```

3. **After extraction** (line ~132):
```python
t_extract = time.time()
# ... existing _extract call ...
logger.info(
    f"EVENT=vision_extraction | mermaid_length={len(mermaid_code)}"
    f" | latency_ms={int((time.time() - t_extract) * 1000)}"
)
```

4. **After merge decision** (in `_merge_or_replace`):
```python
logger.info(
    f"EVENT=vision_merge | action={'keep_existing' if kept else 'replace'}"
    f" | new_edges={new_edges} | existing_edges={existing_edges}"
)
```

5. **Pipeline complete** (end of `process_received_frame`):
```python
logger.info(
    f"EVENT=vision_pipeline_complete | total_latency_ms={elapsed_ms}"
    f" | scene_type={scene_type} | mermaid_length={len(mermaid_code)}"
)
```

6. **Error** (in `_extract` except block, replacing `print()`):
```python
logger.warning(f"EVENT=vision_extraction_error | error={e}")
```

### Dependencies
- None (independent of Phase 1 and 2)

### Files
| File | Change |
|------|--------|
| `src/vision/vision_state_capture.py` | Replace print() with structured EVENT= logging |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Redis down → transcript bridge fails silently | Low | Low | Fire-and-forget on client; try/except on server; vision pipeline still works without transcript (graceful degradation) |
| Timer accuracy on mobile browsers | Low | Low | ±1s drift acceptable; visual display is sufficient |
| Brainstorming timer starts before user begins talking | Medium | Medium | Timer starts at session activation (permissions check pass); Gemini greeting is at +10s, so user effectively has 2:05 of talking time |
| Auto-workflow runs on empty/invalid diagram after timer | Low | Medium | Gate checks `diagramValid` before triggering workflow |

## Success Criteria

1. **Transcript in Redis**: During an ephemeral session, `GET /state/mermaid` response reflects user's verbal descriptions (not just camera frames)
2. **Timer visible**: Countdown timer appears in header, transitions green → yellow (warning) → blue (complete)
3. **Single workflow**: Auto-workflow fires exactly once after brainstorming timer expires
4. **Vision capture gated**: `capture_and_analyze_frame` returns `brainstorming_complete` after 2:15
5. **Cloud Logging**: `EVENT=vision_*` entries visible in GCP Logs Explorer with latency and stage data
6. **No regression**: Server-to-server solution unaffected (no changes to `static/index.html` or WebSocket `/live` handler)

---

## Execution Order

```
Phase 1.1  Fix get_recent_transcript() filter     ─┐
Phase 1.2  Add POST /api/transcript endpoint       ─┤── Can be done together
Phase 1.3  Add client-side transcript relay         ─┘
                         │
Phase 2.1  Add timer constants and state            ─┐
Phase 2.2  Add timer UI element + CSS               ─┤
Phase 2.3  Add timer start/stop/update functions     ─┤── Depends on Phase 1
Phase 2.4  Hook timer into session lifecycle         ─┤
Phase 2.5  Gate capture_and_analyze_frame tool       ─┤
Phase 2.6  Suppress debounce after brainstorming     ─┘
                         │
Phase 3.1  Add structured logger                     ─┐── Independent (parallel OK)
Phase 3.2  Instrument pipeline stages                ─┘
```

## Handoff

- Run `/project` to ingest this plan into the kanban board for implementation tracking
