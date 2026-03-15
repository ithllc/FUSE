# Technical Implementation Plan: Tool Event Logging

**PRD**: `docs/architecture/ephemeral_tokens/PRD_TOOL_EVENT_LOGGING.md`
**Issue**: #30
**Date**: 2026-03-15

---

## Overview

Add a `POST /api/tool-event` endpoint and client-side reporting so every Gemini function call is logged server-side for Cloud Logging observability.

---

## Phase 1: Server-Side Endpoint (main.py)

### 1.1 New Endpoint

**Insert after**: `POST /api/session-event` (line ~1085), before `run_periodic_validation()`

```python
# --- Tool Call Event Logging (Issue #30) ---
_VALID_TOOL_FUNCTIONS = {"capture_and_analyze_frame", "get_session_context", "set_proxy_object"}

@app.post("/api/tool-event")
async def log_tool_event(request: Request):
    """Receives client-side Gemini tool call telemetry for centralized logging.

    The ephemeral token page handles tool calls in the browser. This endpoint
    bridges tool call events into server logs for Cloud Logging observability.
    """
    try:
        body = await request.body()
        if len(body) > 2048:
            return {"status": "error", "message": "Payload too large (max 2KB)"}

        data = json.loads(body)
        func_name = data.get("function_name", "")

        if not func_name:
            return {"status": "error", "message": "Missing function_name"}

        if func_name not in _VALID_TOOL_FUNCTIONS:
            return {"status": "error", "message": f"Unknown function: {func_name}"}

        client_ip = request.client.host
        args = json.dumps(data.get("arguments", {}))
        status = data.get("result_status", "unknown")
        latency = data.get("latency_ms", 0)
        call_id = data.get("call_id", "n/a")

        logger.info(
            f"EVENT=ephemeral_tool_call"
            f" | function={func_name}"
            f" | args={args}"
            f" | status={status}"
            f" | latency_ms={latency}"
            f" | call_id={call_id}"
            f" | client_ip={client_ip}"
        )

        return {"status": "ok"}
    except json.JSONDecodeError:
        return {"status": "error", "message": "Invalid JSON"}
    except Exception as e:
        logger.warning(f"EVENT=tool_event_error | error={e}")
        return {"status": "error", "message": str(e)}
```

---

## Phase 2: Client-Side Reporting (index_ephemeral_tokens.html)

### 2.1 Add Timing and Reporting

In the tool call handler (inside the `for (const fc of functionCalls)` loop), wrap the existing logic with `performance.now()` timing and add a fire-and-forget POST after the tool response is sent to Gemini.

**Current code** (line ~1357):
```javascript
ws.send(JSON.stringify(toolResponse));
addConnectionLog('TOOL: ' + funcName + ' → ' + result.status + ' (response sent to Gemini)', 'ok');
```

**New code** — add timing at the start of the loop and reporting after send:
```javascript
// At the start of the for loop, before stub logic:
const _toolT0 = performance.now();

// After ws.send(toolResponse) and addConnectionLog:
const _toolMs = Math.round(performance.now() - _toolT0);
fetch(BASE + '/api/tool-event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        function_name: funcName,
        arguments: funcArgs,
        result_status: result.status || 'unknown',
        latency_ms: _toolMs,
        call_id: callId
    }),
    keepalive: true
}).catch(() => {});
```

---

## Phase 3: Testing

### Unit Tests

| ID | Test | Input | Expected Output | Pass Criteria |
|----|------|-------|-----------------|---------------|
| UT-1 | Valid tool event | `POST /api/tool-event` with `{"function_name":"capture_and_analyze_frame","arguments":{"mode":"whiteboard"},"result_status":"success","latency_ms":45,"call_id":"fc1"}` | `{"status":"ok"}` | 200, log contains `EVENT=ephemeral_tool_call \| function=capture_and_analyze_frame` |
| UT-2 | Missing function_name | `POST /api/tool-event` with `{"result_status":"success"}` | `{"status":"error","message":"Missing function_name"}` | 200, error returned |
| UT-3 | Unknown function | `POST /api/tool-event` with `{"function_name":"hack_the_planet"}` | `{"status":"error","message":"Unknown function: hack_the_planet"}` | 200, rejected |
| UT-4 | Payload too large | 3KB JSON body | `{"status":"error","message":"Payload too large (max 2KB)"}` | 200, rejected |
| UT-5 | Malformed JSON | `POST /api/tool-event` with `not-json` | `{"status":"error","message":"Invalid JSON"}` | 200, rejected |
| UT-6 | Missing optional fields | `{"function_name":"get_session_context"}` | `{"status":"ok"}` | 200, logged with defaults (latency_ms=0, call_id=n/a) |
| UT-7 | All 3 functions accepted | One POST per known function | All return `{"status":"ok"}` | All 3 logged |

### Integration Tests

| ID | Test | Steps | Pass Criteria |
|----|------|-------|---------------|
| IT-1 | Tool call → server log | 1. Start session<br>2. Say "look at my desk"<br>3. Gemini calls `capture_and_analyze_frame` | `EVENT=ephemeral_tool_call \| function=capture_and_analyze_frame` appears in server log |
| IT-2 | Proxy assignment → server log | 1. Say "the cup is our database"<br>2. Gemini calls `set_proxy_object` | `EVENT=ephemeral_tool_call \| function=set_proxy_object \| args={"object_name":"cup","technical_role":"database"}` in log |
| IT-3 | Session context → server log | 1. Say "what have we assigned so far?"<br>2. Gemini calls `get_session_context` | `EVENT=ephemeral_tool_call \| function=get_session_context` in log |
| IT-4 | Latency captured | Check log for any tool event | `latency_ms` field is > 0 |
| IT-5 | No audio impact | During tool call, audio continues | No audible gaps or delays during tool execution |

### Test Commands

```bash
# UT-1: Valid tool event
curl -s -X POST http://localhost:8080/api/tool-event \
  -H "Content-Type: application/json" \
  -d '{"function_name":"capture_and_analyze_frame","arguments":{"mode":"whiteboard"},"result_status":"success","latency_ms":45,"call_id":"test1"}'

# UT-2: Missing function_name
curl -s -X POST http://localhost:8080/api/tool-event \
  -H "Content-Type: application/json" \
  -d '{"result_status":"success"}'

# UT-3: Unknown function
curl -s -X POST http://localhost:8080/api/tool-event \
  -H "Content-Type: application/json" \
  -d '{"function_name":"hack_the_planet"}'

# UT-7: All 3 functions
for fn in capture_and_analyze_frame get_session_context set_proxy_object; do
  curl -s -X POST http://localhost:8080/api/tool-event \
    -H "Content-Type: application/json" \
    -d "{\"function_name\":\"$fn\",\"result_status\":\"success\",\"latency_ms\":10}"
done

# Check logs
grep "EVENT=ephemeral_tool_call" /tmp/fuse_server.log
```

---

## Implementation Checklist

- [ ] **1.1**: Add `POST /api/tool-event` endpoint to `main.py`
- [ ] **2.1**: Add timing + fire-and-forget reporting in HTML tool call handler
- [ ] **3**: Run unit test commands and verify logs
