# PRD: Tool Event Logging for Ephemeral Token Page

**Issue**: #30
**Status**: Draft
**Author**: FUSE Team
**Date**: 2026-03-15
**Priority**: P1 — Observability (function calling audit trail)

---

## 1. Problem Statement

The FUSE ephemeral token page connects browsers directly to Gemini's Live API. When Gemini invokes function calls (`capture_and_analyze_frame`, `get_session_context`, `set_proxy_object`), the entire tool call lifecycle — request, execution, and response — happens in the browser. The server has zero visibility into:

- Which functions Gemini is calling and how often
- What arguments are being passed (e.g., which vision mode)
- Whether tool calls succeed or fail
- How long tool execution takes (latency)
- Which clients are triggering tool calls

Without this data, operators cannot monitor function calling behavior during demos, diagnose tool failures post-session, or track usage patterns for optimization.

## 2. Solution

Add a dedicated `POST /api/tool-event` endpoint that receives tool call telemetry from the browser and logs it in the existing structured `EVENT=` format. The browser fires a non-blocking `fetch()` after each tool call completes, capturing function name, arguments, result, and timing.

## 3. User Stories

| ID | Story | Acceptance Criteria |
|----|-------|-------------------|
| US-1 | As an operator, I want to see which functions Gemini calls during a session | Each tool call logged with function name, args, and client IP |
| US-2 | As an operator, I want to see tool call success/failure rates | Result status (success/error) logged for every call |
| US-3 | As an operator, I want to measure tool call latency | `latency_ms` field logged for performance monitoring |
| US-4 | As an operator, I want to filter tool events in Cloud Logging | All logs use `EVENT=ephemeral_tool_call` for consistent filtering |
| US-5 | As a developer, I want tool logging to not impact audio performance | Fire-and-forget fetch with `keepalive: true`, no `await` |

## 4. Technical Requirements

### 4.1 Endpoint

```
POST /api/tool-event
Content-Type: application/json
```

### 4.2 Request Body

```json
{
  "function_name": "capture_and_analyze_frame",
  "arguments": {"mode": "whiteboard"},
  "result_status": "success",
  "latency_ms": 45,
  "call_id": "fc_abc123"
}
```

### 4.3 Validation

| Rule | Action |
|------|--------|
| Payload > 2KB | Reject with 400 |
| Unknown `function_name` | Reject with 400 |
| Missing `function_name` | Reject with 400 |
| Malformed JSON | Reject with 400 |
| Missing optional fields | Accept, log with defaults |

**Known function names**: `capture_and_analyze_frame`, `get_session_context`, `set_proxy_object`

### 4.4 Server Log Format

```
EVENT=ephemeral_tool_call | function=capture_and_analyze_frame | args={"mode":"whiteboard"} | status=success | latency_ms=45 | call_id=fc_abc123 | client_ip=172.29.0.1
```

### 4.5 Client-Side Integration

After each tool call response is sent back to Gemini, fire a non-blocking POST:

```javascript
fetch(BASE + '/api/tool-event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ... }),
    keepalive: true
}).catch(() => {});
```

### 4.6 Response

```json
{"status": "ok"}
```

## 5. File Inventory

| File | Action | Description |
|------|--------|-------------|
| `main.py` | Append endpoint | Add `POST /api/tool-event` |
| `static/index_ephemeral_tokens.html` | Add reporting in tool call handler | Fire-and-forget POST after each tool call |
| `docs/architecture/ephemeral_tokens/PRD_TOOL_EVENT_LOGGING.md` | New | This document |
| `docs/architecture/ephemeral_tokens/TECHNICAL_PLAN_TOOL_LOGGING.md` | New | Implementation plan |

## 6. Success Metrics

- Every tool call produces a corresponding `EVENT=ephemeral_tool_call` in Cloud Logging
- Tool events are filterable by function name: `textPayload:"function=capture_and_analyze_frame"`
- Zero impact on audio latency (fire-and-forget, no await)
- Payload validation rejects invalid requests

## 7. Out of Scope

- Tool call rate limiting (handled by Gemini's own limits)
- Tool response body logging (may contain large data like mermaid code)
- Authentication on the endpoint (hackathon scope)
