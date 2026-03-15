# Technical Implementation Plan: UAT Observability Slice

**PRD Reference**: Targeted slice of Phase 1 Production Hardening (`docs/fuse_standalone_product_plan/FUSE_STANDALONE_PRODUCT_ROADMAP.md`)
**Date**: 2026-03-11
**Status**: Implemented
**Scope**: Hackathon UAT — minimum viable observability for testing and demo debugging
**Deadline**: Before March 16, 2026

---

## Overview

FUSE currently has **zero client-facing diagnostic visibility**. When a session fails (e.g., WebSocket connects then immediately disconnects), users see only "Disconnected" with no indication of what went wrong. Server-side errors are logged to stderr (Cloud Logging) but are invisible to testers.

This plan adds a lightweight observability layer that surfaces enough information for:
1. **Testers** to report actionable bug reports ("Gemini Live returned 403" vs "it's broken")
2. **Demo operators** to verify system readiness before a live demo
3. **Developers** to diagnose issues without accessing Cloud Logging

The implementation touches 3 existing files and creates 0 new modules — everything is added to existing components.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Browser UI (index.html)                        │
│                                                 │
│  ┌──────────────┐  ┌────────────────────────┐  │
│  │ Status Badge  │  │ System Status Panel    │  │
│  │ (existing)    │  │ (NEW - collapsible)    │  │
│  │               │  │                        │  │
│  │ ● Connected   │  │ Redis: ● OK (2ms)     │  │
│  │               │  │ Gemini Live: ● OK      │  │
│  │               │  │ Gemini Vision: ● OK    │  │
│  │               │  │ Imagen: ● OK           │  │
│  │               │  │ Veo3: ● OK             │  │
│  │               │  │                        │  │
│  │               │  │ Vision Mode: auto      │  │
│  │               │  │ Proxies: 3             │  │
│  │               │  │ Diagram: 450 chars     │  │
│  │               │  │                        │  │
│  │               │  │ ─── Connection Log ─── │  │
│  │               │  │ 01:23 WS connected     │  │
│  │               │  │ 01:23 Live session OK  │  │
│  │               │  │ 01:24 Frame processed  │  │
│  │               │  │ 01:25 WS error: 403   │  │
│  └──────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────┘
         │                       │
         │ WebSocket /live       │ GET /health
         │ (structured errors)   │ (deep check)
         ▼                       ▼
┌─────────────────────────────────────────────────┐
│  FastAPI Server (main.py)                       │
│                                                 │
│  /health ──► Check Redis ping                   │
│          ──► Check globals != None              │
│          ──► Return component-level status       │
│                                                 │
│  /live   ──► Send stage-by-stage status msgs    │
│          ──► Send structured error before close  │
│          ──► Log errors as session events        │
└─────────────────────────────────────────────────┘
```

---

## File Manifest

| Action | File | Changes |
|--------|------|---------|
| **Modify** | `main.py` | Rewrite `/health` endpoint; add structured error messages to WebSocket handler; add error event logging |
| **Modify** | `static/index.html` | Add System Status panel; add connection stage tracking; display structured errors; add WebSocket close code/reason handling |
| **Modify** | `src/state/session_state_manager.py` | Add `get_session_diagnostics()` method returning aggregated session state for the UI |

---

## Phase 1: Enhanced Health Check

### Objectives
- Replace the static `/health` response with a deep component check
- Verify Redis connectivity, global handler initialization, and model client readiness
- Return component-level status with latency metrics

### Implementation

#### Step 1.1: Rewrite `/health` in `main.py`

```python
@app.get("/health")
async def health_check():
    """Deep health check — verifies all downstream components."""
    components = {}

    # 1. Redis
    try:
        if state_manager:
            t0 = time.time()
            state_manager.r.ping()
            latency_ms = int((time.time() - t0) * 1000)
            components["redis"] = {"status": "ok", "latency_ms": latency_ms}
        else:
            components["redis"] = {"status": "error", "detail": "State manager not initialized"}
    except Exception as e:
        components["redis"] = {"status": "error", "detail": str(e)}

    # 2. Component initialization checks (are globals non-None?)
    component_checks = {
        "gemini_live": live_handler,
        "gemini_vision": vision_capture,
        "gemini_pro": proof_orchestrator,
        "diagram_renderer": diagram_renderer,
        "imagen": imagen_visualizer,
        "veo3": veo3_animator,
    }
    for name, handler in component_checks.items():
        if handler is not None:
            components[name] = {"status": "ok"}
        else:
            components[name] = {"status": "error", "detail": "Not initialized"}

    # 3. Session state summary (if Redis is up)
    session = {}
    if state_manager and components["redis"]["status"] == "ok":
        try:
            session["vision_mode"] = state_manager.get_vision_mode()
            session["proxy_count"] = len(state_manager.get_proxy_registry())
            arch_state = state_manager.get_architectural_state()
            session["diagram_length"] = len(arch_state) if arch_state else 0
            session["recent_events"] = len(state_manager.get_events(limit=10))
        except Exception:
            pass

    # Overall status
    all_ok = all(c.get("status") == "ok" for c in components.values())
    overall = "ok" if all_ok else "degraded"

    return {
        "status": overall,
        "system": "FUSE",
        "project_id": PROJECT_ID,
        "components": components,
        "session": session,
    }
```

**Key decisions:**
- Redis check uses `PING` command — cheapest possible round-trip
- Component checks only verify initialization (non-None), NOT model API connectivity (that would add latency)
- Session summary gives a quick snapshot without heavy queries
- `"degraded"` vs `"ok"` lets the UI show an amber vs green indicator

### Dependencies
- None (this is the foundation)

---

## Phase 2: Structured WebSocket Error Reporting

### Objectives
- Send stage-by-stage connection status messages through the WebSocket so the client knows exactly where the connection succeeded or failed
- Send structured error JSON (with error type, stage, and detail) before closing the WebSocket
- Log errors as session events for post-mortem analysis

### Implementation

#### Step 2.1: Add connection stage messages in `/live` handler

Update the WebSocket handler in `main.py` to send structured status messages at each connection stage:

```python
@app.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    # Stage 1: Check handler initialization
    if not live_handler:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "error",
            "stage": "initialization",
            "message": "Live handler not initialized. Server may still be starting up.",
            "detail": "The GeminiLiveStreamHandler failed to initialize during server startup. Check server logs."
        }))
        await websocket.close(code=1011)
        return

    await websocket.accept()
    logger.info("WebSocket connection established.")

    try:
        # Stage 2: Notify client we're connecting to Gemini
        await websocket.send_text(json.dumps({
            "type": "status",
            "stage": "connecting",
            "message": "Connecting to Gemini Live API..."
        }))

        async with live_handler.client.aio.live.connect(
            model=live_handler.model_id,
            config=live_handler.get_config()
        ) as session:
            # Stage 3: Gemini session established
            logger.info("Gemini Live session connected successfully.")
            await websocket.send_text(json.dumps({
                "type": "status",
                "stage": "connected",
                "message": "[FUSE] Live session active. You can speak or type.",
                "model": live_handler.model_id,
                "location": live_handler.location
            }))

            # ... existing receive_from_client / send_to_client ...

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        error_stage = "gemini_connect"
        logger.error(f"Live session error at stage '{error_stage}': {error_msg}\n{traceback.format_exc()}")

        # Log as session event for diagnostics
        if state_manager:
            state_manager.log_event("connection_error", {
                "stage": error_stage,
                "error_type": type(e).__name__,
                "detail": str(e),
            })

        # Send structured error to client before closing
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "stage": error_stage,
                "message": f"Live session failed: {error_msg}",
                "error_type": type(e).__name__,
                "detail": str(e)
            }))
        except Exception:
            pass
    finally:
        logger.info("WebSocket connection closed.")
```

#### Step 2.2: Add error event logging

Add a new event type `connection_error` to the session event log. No changes to `SessionStateManager` are needed — `log_event()` already accepts any event type string. The new event payloads include:

```json
{
  "type": "connection_error",
  "timestamp": "ISO-8601",
  "payload": {
    "stage": "gemini_connect",
    "error_type": "PermissionDenied",
    "detail": "403 Forbidden: Gemini Live API access denied for service account"
  }
}
```

**Key decisions:**
- Messages use `"type": "status"` for progress and `"type": "error"` for failures — the UI can distinguish them from regular `"text"` messages
- The `"stage"` field tells the user exactly WHERE the failure occurred
- Error events are persisted to Redis so they survive WebSocket disconnection and can be retrieved via `/health`

### Dependencies
- Phase 1 (health endpoint should be ready for diagnostics panel to call)

---

## Phase 3: Client-Side Diagnostics UI

### Objectives
- Add a collapsible "System Status" panel to the UI
- Track and display WebSocket connection stages
- Parse structured error messages and display them meaningfully
- Show component health from `/health`
- Display WebSocket close code and reason

### Implementation

#### Step 3.1: Add System Status panel HTML

Add a collapsible diagnostics panel to the header area in `static/index.html`:

```html
<!-- In header, next to status badge -->
<button class="btn btn-sm" onclick="toggleSystemStatus()" title="System Status">
    &#9881; Status
</button>

<!-- Below header, collapsible -->
<div id="systemStatusPanel" style="display:none;">
    <div class="panel" style="margin:0 16px; border-radius:0 0 12px 12px; border-top:none;">
        <div class="panel-body" style="padding:12px 16px;">
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
                <!-- Component Health -->
                <div>
                    <h3 style="font-size:12px; color:#8b949e; margin-bottom:8px; text-transform:uppercase;">Components</h3>
                    <div id="componentHealth" style="font-size:13px; line-height:2;">Loading...</div>
                </div>
                <!-- Session Info -->
                <div>
                    <h3 style="font-size:12px; color:#8b949e; margin-bottom:8px; text-transform:uppercase;">Session</h3>
                    <div id="sessionInfo" style="font-size:13px; line-height:2;">No session data</div>
                </div>
            </div>
            <!-- Connection Log -->
            <div style="margin-top:12px;">
                <h3 style="font-size:12px; color:#8b949e; margin-bottom:8px; text-transform:uppercase;">Connection Log</h3>
                <div id="connectionLog" style="font-family:monospace; font-size:12px; max-height:120px; overflow-y:auto; background:#0d1117; border-radius:6px; padding:8px; color:#8b949e;">
                    No events yet.
                </div>
            </div>
        </div>
    </div>
</div>
```

#### Step 3.2: Add System Status CSS

```css
#systemStatusPanel .health-ok { color: #3fb950; }
#systemStatusPanel .health-error { color: #f85149; }
#systemStatusPanel .health-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 6px;
}
#systemStatusPanel .health-dot.ok { background: #3fb950; }
#systemStatusPanel .health-dot.error { background: #f85149; }
```

#### Step 3.3: Add JavaScript for diagnostics

```javascript
// --- System Status / Diagnostics ---
let connectionLog = [];

function toggleSystemStatus() {
    const panel = document.getElementById('systemStatusPanel');
    const isVisible = panel.style.display !== 'none';
    panel.style.display = isVisible ? 'none' : 'block';
    if (!isVisible) refreshSystemStatus();
}

async function refreshSystemStatus() {
    try {
        const resp = await fetch(BASE + '/health');
        const data = await resp.json();
        renderComponentHealth(data.components || {});
        renderSessionInfo(data.session || {});
    } catch (e) {
        document.getElementById('componentHealth').innerHTML =
            '<span class="health-error">Failed to fetch health: ' + e.message + '</span>';
    }
}

function renderComponentHealth(components) {
    const el = document.getElementById('componentHealth');
    const names = {
        redis: 'Redis', gemini_live: 'Gemini Live', gemini_vision: 'Gemini Vision',
        gemini_pro: 'Gemini Pro', diagram_renderer: 'Diagram Renderer',
        imagen: 'Imagen 4.0', veo3: 'Veo 3.0'
    };
    let html = '';
    for (const [key, info] of Object.entries(components)) {
        const ok = info.status === 'ok';
        const label = names[key] || key;
        const detail = ok
            ? (info.latency_ms !== undefined ? ` (${info.latency_ms}ms)` : '')
            : ` — ${info.detail || 'Unknown error'}`;
        html += `<div><span class="health-dot ${ok ? 'ok' : 'error'}"></span>${label}${detail}</div>`;
    }
    el.innerHTML = html || 'No components reported.';
}

function renderSessionInfo(session) {
    const el = document.getElementById('sessionInfo');
    if (!session || Object.keys(session).length === 0) {
        el.textContent = 'No session data available.';
        return;
    }
    el.innerHTML = [
        `Vision Mode: <strong>${session.vision_mode || 'N/A'}</strong>`,
        `Proxy Objects: <strong>${session.proxy_count ?? 'N/A'}</strong>`,
        `Diagram Length: <strong>${session.diagram_length ?? 0} chars</strong>`,
        `Recent Events: <strong>${session.recent_events ?? 0}</strong>`,
    ].join('<br>');
}

function addConnectionLog(message, level) {
    const ts = new Date().toLocaleTimeString('en-US', {hour12: false, hour:'2-digit', minute:'2-digit', second:'2-digit'});
    const color = level === 'error' ? '#f85149' : level === 'ok' ? '#3fb950' : '#8b949e';
    connectionLog.push({ ts, message, color });
    // Keep last 50 entries
    if (connectionLog.length > 50) connectionLog.shift();
    renderConnectionLog();
}

function renderConnectionLog() {
    const el = document.getElementById('connectionLog');
    if (connectionLog.length === 0) {
        el.textContent = 'No events yet.';
        return;
    }
    el.innerHTML = connectionLog.map(e =>
        `<div style="color:${e.color}">${e.ts} ${e.message}</div>`
    ).join('');
    el.scrollTop = el.scrollHeight;
}
```

#### Step 3.4: Update WebSocket message handler to parse structured messages

Update the existing `ws.onmessage` handler to detect `type: "status"` and `type: "error"` messages:

```javascript
ws.onmessage = (event) => {
    if (typeof event.data === 'string') {
        try {
            const data = JSON.parse(event.data);

            // Handle structured status messages
            if (data.type === 'status') {
                addConnectionLog(data.message, 'ok');
                addMsg('system', data.message);
                return;
            }

            // Handle structured error messages
            if (data.type === 'error') {
                addConnectionLog(`[${data.stage}] ${data.message}`, 'error');
                addMsg('system', `Error (${data.stage}): ${data.message}`);
                return;
            }

            // Handle regular text messages (existing behavior)
            if (data.text) {
                addMsg('fuse', data.text);
                checkForMermaid(data.text);
            }
        } catch (e) {
            addMsg('fuse', event.data);
        }
    } else if (event.data instanceof ArrayBuffer) {
        playAudioResponse(event.data);
    }
};
```

#### Step 3.5: Update WebSocket `onclose` to capture close code and reason

```javascript
ws.onclose = (event) => {
    const wasActive = sessionState === 'active';
    setStatus(false);

    // Log close code and reason for diagnostics
    const reason = event.reason || 'No reason provided';
    const codeMap = {
        1000: 'Normal closure',
        1001: 'Going away',
        1006: 'Abnormal closure (no close frame)',
        1008: 'Policy violation',
        1011: 'Server error',
        1012: 'Service restart',
        1013: 'Try again later',
        1014: 'Bad gateway',
    };
    const codeDesc = codeMap[event.code] || `Code ${event.code}`;
    addConnectionLog(`WebSocket closed: ${codeDesc} — ${reason}`, event.code === 1000 ? 'ok' : 'error');
    addMsg('system', `Disconnected: ${codeDesc}`);

    // ... rest of existing onclose logic ...
};
```

#### Step 3.6: Update `ws.onerror` to log more context

```javascript
ws.onerror = (event) => {
    addConnectionLog('WebSocket error (check browser console for details)', 'error');
    addMsg('system', 'WebSocket connection error. See System Status for details.');
};
```

### Dependencies
- Phase 1 (`/health` endpoint must return component data)
- Phase 2 (structured WebSocket messages must be sent by server)

---

## Phase 4: Session Diagnostics Helper

### Objectives
- Add a convenience method to `SessionStateManager` that aggregates session state for the diagnostics panel
- Add recent error events to the health check response

### Implementation

#### Step 4.1: Add `get_session_diagnostics()` to `session_state_manager.py`

```python
def get_session_diagnostics(self) -> Dict[str, Any]:
    """Returns aggregated session state for the diagnostics UI."""
    diagnostics = {
        "vision_mode": self.get_vision_mode(),
        "proxy_count": len(self.get_proxy_registry()),
        "proxy_registry": self.get_proxy_registry(),
    }

    arch_state = self.get_architectural_state()
    diagnostics["diagram_length"] = len(arch_state) if arch_state else 0

    # Recent events with error filtering
    events = self.get_events(limit=20)
    diagnostics["total_events"] = len(events)
    diagnostics["recent_errors"] = [
        e for e in events if e.get("type") == "connection_error"
    ][:5]
    diagnostics["last_event"] = events[0] if events else None

    return diagnostics
```

### Dependencies
- None (standalone, but consumed by Phase 1 health endpoint and Phase 3 UI)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Health check adds latency to page load | Low | Low | Health endpoint is only called on-demand (when panel opened), not on page load |
| Structured messages break existing text parsing | Medium | Medium | Use explicit `"type"` field; existing `data.text` handling is the fallback |
| Error messages expose sensitive info | Low | Medium | Only expose error type and stage, not stack traces or credentials |
| Diagnostics panel clutters the UI | Low | Low | Panel is hidden by default, toggled via gear icon in header |
| Redis PING adds overhead per health check | Low | Low | Single PING is <1ms; health endpoint is not called in hot path |

---

## Success Criteria

| Metric | Target |
|--------|--------|
| User can identify *why* a session failed | Error stage + type shown in UI within 2s of failure |
| User can verify system readiness before demo | `/health` returns component-level status; all green = ready |
| Connection errors are logged as events | `connection_error` events appear in Redis and diagnostics panel |
| WebSocket close code is visible | Close code + reason shown in connection log |
| Zero regressions to existing functionality | Existing text/audio WebSocket flow unchanged |

---

## Implementation Order

```
Phase 4 ─────► Phase 1 ─────► Phase 2 ─────► Phase 3
(Diagnostics    (Health        (WebSocket      (UI Panel +
 helper method)  endpoint)      error msgs)     client-side)
```

Phase 4 is independent and can be built first. Phases 1-3 are sequential: the health endpoint feeds the UI panel, and the structured WebSocket messages feed the connection log.

**Estimated effort**: 3-4 hours total across all phases.

---

**Next Step**: Get greenlight from user, then implement starting with Phase 4 → Phase 1 → Phase 2 → Phase 3.
