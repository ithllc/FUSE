# PRD: Structured Cloud Logging for Ephemeral Token Page

**Issue**: #30
**Status**: Draft
**Author**: FUSE Team
**Date**: 2026-03-14
**Hackathon Deadline**: 2026-03-16
**Priority**: P1 — Observability (demo monitoring & post-mortem capability)

---

## 1. Problem Statement

The FUSE ephemeral token page (`/ephemeral`) connects browsers directly to Gemini's Live API, bypassing the server-side WebSocket proxy. While this eliminates audio relay errors, it also eliminates server-side visibility into session lifecycle. The server currently logs HTTP access via uvicorn but lacks structured application logs for:

- Token generation audit trail (who requested, when, how often)
- Ephemeral vs. original page usage differentiation
- Client-side Gemini session lifecycle events (connect, disconnect, errors, duration)
- Vision pipeline performance metrics (processing time, frame size, success/failure)

Without these logs, the team cannot:
- Monitor demo stability during the hackathon presentation
- Diagnose issues post-session (no server-side record of what happened)
- Track token usage patterns or detect abuse
- Identify vision pipeline bottlenecks

## 2. Solution

Add structured JSON logging to five areas of the ephemeral token flow. All logs use Python's `logging` module (already configured to write to stderr, which Cloud Run captures into Cloud Logging). A new lightweight endpoint (`POST /api/session-event`) allows the browser to report client-side session lifecycle events back to the server for centralized logging.

## 3. User Stories

| ID | Story | Acceptance Criteria |
|----|-------|-------------------|
| US-1 | As an operator, I want to see when ephemeral tokens are created so I can track usage | Token creation logs include timestamp, token hash, expiry, client IP |
| US-2 | As an operator, I want to distinguish ephemeral page loads from original page loads | Structured log entry when `/ephemeral` is served, with client metadata |
| US-3 | As an operator, I want to see client-side Gemini session events in server logs | Browser POSTs session events (connect, disconnect, error) to server; server logs them |
| US-4 | As an operator, I want to see vision frame processing performance | Each frame logs duration, size, and outcome (success/timeout/error) |
| US-5 | As an operator, I want all logs in a consistent JSON format for Cloud Logging queries | All new logs follow `{"event": "...", "data": {...}}` pattern |

## 4. Technical Requirements

### 4.1 Log Format

All structured logs use this pattern for Cloud Logging filterability:

```python
logger.info(f"EVENT={event_name} | {key1}={value1} | {key2}={value2}")
```

This format is grep-friendly, Cloud Logging filterable, and human-readable in terminal output.

### 4.2 Logging Points

#### 4.2.1 Ephemeral Token Created (Gap #1 + #3)

**When**: After successful `auth_tokens.create()` in `GET /api/ephemeral-token`
**Fields**:
- `event`: `ephemeral_token_created`
- `token_prefix`: First 12 chars of token (for correlation, not security-sensitive)
- `expires_in_seconds`: 1800
- `client_ip`: From `request.client.host`
- `user_agent`: From `request.headers.get("user-agent")`

**When**: Token creation fails
**Fields**:
- `event`: `ephemeral_token_failed`
- `error`: Exception message
- `client_ip`: From `request.client.host`

#### 4.2.2 Ephemeral Page Served (Gap #2)

**When**: `GET /ephemeral` is served successfully
**Fields**:
- `event`: `ephemeral_page_served`
- `client_ip`: From `request.client.host`
- `user_agent`: From `request.headers.get("user-agent")`

#### 4.2.3 Client-Side Session Events (Gap #4)

**New endpoint**: `POST /api/session-event`

**Request body** (JSON):
```json
{
  "event": "session_connect|session_disconnect|session_error|session_active",
  "detail": "optional detail string",
  "duration_seconds": 0,
  "audio_chunks_sent": 0,
  "audio_chunks_received": 0,
  "latency_avg_ms": 0
}
```

**Server logs**:
- `event`: `ephemeral_session_{event}`
- All request body fields
- `client_ip`: From `request.client.host`

**Validation**: Only accept known event types. Reject payloads > 1KB. No authentication required (hackathon demo).

#### 4.2.4 Vision Frame Processing (Gap #5)

**When**: After `process_received_frame()` completes (success or failure)
**Fields**:
- `event`: `vision_frame_processed`
- `duration_ms`: Processing time in milliseconds
- `frame_size_bytes`: Input frame size
- `outcome`: `success|timeout|error`
- `mermaid_length`: Output length (on success)

### 4.3 Non-Requirements

- No log aggregation or dashboard setup (Cloud Logging provides this)
- No authentication on session-event endpoint (hackathon scope)
- No log rotation (Cloud Run handles this)
- No changes to existing logging statements

## 5. File Inventory

| File | Action | Description |
|------|--------|-------------|
| `main.py` | Append new endpoint + modify token/vision endpoints | Add `POST /api/session-event`, add structured logging to existing endpoints |
| `static/index_ephemeral_tokens.html` | Add session event reporting | POST lifecycle events to `/api/session-event` |
| `docs/architecture/ephemeral_tokens/PRD_CLOUD_LOGGING.md` | New | This document |
| `docs/architecture/ephemeral_tokens/TECHNICAL_PLAN_LOGGING.md` | New | Implementation plan |

## 6. Success Metrics

- All 5 logging points produce output visible in `stderr` / Cloud Logging
- Token creation, page loads, and session events are filterable by `EVENT=ephemeral_*`
- Vision frame logs include timing data for performance analysis
- Zero impact on request latency (logging is non-blocking)

## 7. Risks

| Risk | Mitigation |
|------|------------|
| Session-event endpoint abused for spam | Payload size limit (1KB), rate limiting via Cloud Run concurrency |
| Logging sensitive data (full token) | Only log token prefix (first 12 chars) |
| Client-side events unreliable (user closes tab) | `navigator.sendBeacon` for disconnect events; accept partial data |
