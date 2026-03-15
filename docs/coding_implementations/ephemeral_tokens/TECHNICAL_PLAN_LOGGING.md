# Technical Implementation Plan: Structured Cloud Logging

**PRD**: `docs/architecture/ephemeral_tokens/PRD_CLOUD_LOGGING.md`
**Issue**: #30
**Date**: 2026-03-14

---

## Overview

Add structured logging to 5 points in the ephemeral token flow. Server-side changes are minimal inline additions to 3 existing endpoints plus 1 new endpoint. Client-side changes add session event reporting to the ephemeral HTML page.

## Log Format Convention

All new logs follow this pipe-delimited format for grep/Cloud Logging filterability:

```python
logger.info(f"EVENT=ephemeral_token_created | token_prefix={token.name[:12]} | client_ip={ip}")
```

---

## Phase 1: Server-Side Logging (main.py)

### 1.1 Token Endpoint Logging (Gap #1 + #3)

**File**: `main.py`, function `create_ephemeral_token()` at line ~973
**Change**: Add `Request` parameter, log success/failure with client metadata

**Current signature**:
```python
@app.get("/api/ephemeral-token")
async def create_ephemeral_token():
```

**New signature**:
```python
@app.get("/api/ephemeral-token")
async def create_ephemeral_token(request: Request):
```

**Add after successful token creation** (after line ~1001, before the return):
```python
        logger.info(
            f"EVENT=ephemeral_token_created"
            f" | token_prefix={token.name[:12]}"
            f" | expires_in=1800s"
            f" | client_ip={request.client.host}"
            f" | user_agent={request.headers.get('user-agent', 'unknown')[:80]}"
        )
```

**Replace existing error log** (line ~1010):
```python
    except Exception as e:
        logger.error(
            f"EVENT=ephemeral_token_failed"
            f" | error={e}"
            f" | client_ip={request.client.host}"
        )
        return {"status": "error", "message": str(e)}
```

### 1.2 Page Served Logging (Gap #2)

**File**: `main.py`, function `serve_ephemeral_ui()` at line ~964
**Change**: Add `Request` parameter, log page served

**Current signature**:
```python
@app.get("/ephemeral", response_class=HTMLResponse)
async def serve_ephemeral_ui():
```

**New signature**:
```python
@app.get("/ephemeral", response_class=HTMLResponse)
async def serve_ephemeral_ui(request: Request):
```

**Add before the return** (after reading the file, before `return HTMLResponse`):
```python
        logger.info(
            f"EVENT=ephemeral_page_served"
            f" | client_ip={request.client.host}"
            f" | user_agent={request.headers.get('user-agent', 'unknown')[:80]}"
        )
```

### 1.3 Vision Frame Timing (Gap #5)

**File**: `main.py`, function `receive_frame()` at line ~157
**Change**: Add `time.time()` timing around processing, log with frame size

**Add before `_processing_frame = True`** (line ~183):
```python
    _frame_size = len(frame_bytes)
    _frame_t0 = time.time()
```

**Replace the success return** (line ~190):
```python
        _frame_ms = int((time.time() - _frame_t0) * 1000)
        logger.info(
            f"EVENT=vision_frame_processed"
            f" | outcome=success"
            f" | duration_ms={_frame_ms}"
            f" | frame_size={_frame_size}"
            f" | mermaid_length={len(mermaid_code)}"
        )
        return {"status": "success", "mermaid_length": len(mermaid_code)}
```

**Replace the timeout handler** (line ~191-193):
```python
    except asyncio.TimeoutError:
        _frame_ms = int((time.time() - _frame_t0) * 1000)
        logger.warning(
            f"EVENT=vision_frame_processed"
            f" | outcome=timeout"
            f" | duration_ms={_frame_ms}"
            f" | frame_size={_frame_size}"
        )
        return {"status": "error", "message": "Vision processing timed out"}
```

**Replace the error handler** (line ~194-197):
```python
    except Exception as e:
        _frame_ms = int((time.time() - _frame_t0) * 1000)
        error_detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
        logger.warning(
            f"EVENT=vision_frame_processed"
            f" | outcome=error"
            f" | duration_ms={_frame_ms}"
            f" | frame_size={_frame_size}"
            f" | error={error_detail}"
        )
        return {"status": "error", "message": error_detail}
```

### 1.4 Session Event Endpoint (Gap #4)

**File**: `main.py`, new endpoint appended after `create_ephemeral_token()`
**No existing code changes** — purely additive

```python
_VALID_SESSION_EVENTS = {"session_connect", "session_disconnect", "session_error", "session_active"}

@app.post("/api/session-event")
async def log_session_event(request: Request):
    """Receives client-side Gemini session lifecycle events for centralized logging.

    The ephemeral token page connects directly to Gemini (no server WebSocket),
    so session events are only visible client-side. This endpoint bridges them
    into server logs for Cloud Logging observability.
    """
    try:
        body = await request.body()
        if len(body) > 1024:
            return {"status": "error", "message": "Payload too large (max 1KB)"}

        data = json.loads(body)
        event = data.get("event", "unknown")

        if event not in _VALID_SESSION_EVENTS:
            return {"status": "error", "message": f"Unknown event: {event}"}

        client_ip = request.client.host

        # Build structured log line from event data
        parts = [f"EVENT=ephemeral_{event}", f"client_ip={client_ip}"]
        for key in ("detail", "duration_seconds", "audio_chunks_sent",
                     "audio_chunks_received", "latency_avg_ms"):
            if key in data and data[key] is not None:
                parts.append(f"{key}={data[key]}")

        logger.info(" | ".join(parts))

        return {"status": "ok"}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}
    except Exception as e:
        logger.warning(f"EVENT=session_event_error | error={e}")
        return {"status": "error", "message": str(e)}
```

---

## Phase 2: Client-Side Session Reporting (index_ephemeral_tokens.html)

### 2.1 Helper Function

Add a `reportSessionEvent()` helper near the top of the `<script>` block (after the `BASE` constant):

```javascript
// --- Session event reporting for server-side logging (issue #30) ---
let _sessionStartTime = 0;

function reportSessionEvent(event, extraData) {
    const payload = JSON.stringify({
        event: event,
        ...extraData
    });

    // Use sendBeacon for disconnect (survives tab close), fetch for others
    if (event === 'session_disconnect') {
        navigator.sendBeacon(BASE + '/api/session-event', payload);
    } else {
        fetch(BASE + '/api/session-event', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload,
            keepalive: true
        }).catch(() => {}); // Fire-and-forget
    }
}
```

### 2.2 Report Session Connect

In `ws.onmessage`, after `setupComplete` is handled and session transitions to diagnostics:

```javascript
if (msg.setupComplete) {
    // ... existing setupComplete handling ...
    _sessionStartTime = Date.now();
    reportSessionEvent('session_connect', {
        detail: 'setupComplete received'
    });
    return;
}
```

### 2.3 Report Session Disconnect

In `ws.onclose`, after cleanup, before the final state transitions:

```javascript
ws.onclose = (event) => {
    // ... existing close handling ...
    const duration = _sessionStartTime > 0
        ? Math.round((Date.now() - _sessionStartTime) / 1000) : 0;
    reportSessionEvent('session_disconnect', {
        detail: codeDesc + ' — ' + reason,
        duration_seconds: duration,
        audio_chunks_sent: window._audioSendCount || 0,
        audio_chunks_received: latencyAudioResponseCount || 0,
        latency_avg_ms: latencyClientSamples.length > 0
            ? Math.round(latencyClientSamples.reduce((a,b) => a+b, 0) / latencyClientSamples.length)
            : 0
    });
    // ... rest of existing onclose ...
```

### 2.4 Report Session Error

In `ws.onerror`:

```javascript
ws.onerror = (e) => {
    addConnectionLog('Gemini WebSocket error (check browser console)', 'error');
    addMsg('system', 'WebSocket connection error. Check browser console.');
    reportSessionEvent('session_error', {
        detail: 'WebSocket error event'
    });
};
```

### 2.5 Report Session Active (diagnostics passed)

In `finishDiagnostics()`, after `sessionState = 'active'`:

```javascript
sessionState = 'active';
addConnectionLog('Session active', 'ok');
reportSessionEvent('session_active', {
    detail: reason === 'passed' ? 'All diagnostics passed' : 'Diagnostics timed out'
});
```

---

## Phase 3: Testing

### Verification Checklist

| Log Point | How to Verify | Expected Log |
|-----------|---------------|-------------|
| Token created | `curl /api/ephemeral-token` | `EVENT=ephemeral_token_created \| token_prefix=auth_tokens/ \| ...` |
| Token failed | Set `GEMINI_API_KEY=""`, curl | `EVENT=ephemeral_token_failed \| error=... \| ...` |
| Page served | Open `/ephemeral` in browser | `EVENT=ephemeral_page_served \| client_ip=... \| ...` |
| Session connect | Click "Start Session" | `EVENT=ephemeral_session_connect \| client_ip=... \| detail=setupComplete received` |
| Session active | Wait for diagnostics | `EVENT=ephemeral_session_active \| client_ip=... \| detail=All diagnostics passed` |
| Session disconnect | Click "End Session" | `EVENT=ephemeral_session_disconnect \| client_ip=... \| duration_seconds=... \| audio_chunks_sent=...` |
| Session error | Kill network mid-session | `EVENT=ephemeral_session_error \| client_ip=... \| detail=WebSocket error event` |
| Vision frame success | Send camera frame (with Redis) | `EVENT=vision_frame_processed \| outcome=success \| duration_ms=... \| frame_size=... \| mermaid_length=...` |
| Vision frame timeout | Send camera frame (no Redis) | `EVENT=vision_frame_processed \| outcome=timeout \| duration_ms=... \| frame_size=...` |

### Cloud Logging Queries

Once deployed to Cloud Run, these logs are filterable:

```
# All ephemeral events
textPayload:"EVENT=ephemeral_"

# Token creation only
textPayload:"EVENT=ephemeral_token_created"

# Session disconnects with duration
textPayload:"EVENT=ephemeral_session_disconnect"

# Vision frame performance
textPayload:"EVENT=vision_frame_processed"

# Errors only
textPayload:"EVENT=ephemeral_token_failed" OR textPayload:"EVENT=ephemeral_session_error"
```

---

## Implementation Checklist

- [ ] **1.1**: Add `Request` param + logging to `create_ephemeral_token()`
- [ ] **1.2**: Add `Request` param + logging to `serve_ephemeral_ui()`
- [ ] **1.3**: Add timing + logging to `receive_frame()`
- [ ] **1.4**: Add `POST /api/session-event` endpoint
- [ ] **2.1**: Add `reportSessionEvent()` helper to HTML
- [ ] **2.2**: Report `session_connect` on setupComplete
- [ ] **2.3**: Report `session_disconnect` on ws.onclose
- [ ] **2.4**: Report `session_error` on ws.onerror
- [ ] **2.5**: Report `session_active` on diagnostics complete
- [ ] **3**: Run verification checklist
