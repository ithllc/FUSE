# Issues Log — 2026-03-12

## Summary Table

| # | Title | Type | Severity | GitHub | Status |
|---|-------|------|----------|--------|--------|
| 1 | WebSocket keepalive ping timeout causes premature session death | Bug | Blocker | [#20](https://github.com/ithllc/FUSE/issues/20) | Fix implemented, pending deploy |
| 2 | Veo3 animation fails — empty response due to person_generation filter | Bug | Major | [#21](https://github.com/ithllc/FUSE/issues/21) | Fix implemented, pending deploy |

---

## Issue 1: WebSocket keepalive ping timeout causes premature session death

**GitHub**: [#20](https://github.com/ithllc/FUSE/issues/20)
**Type**: Bug | **Severity**: Blocker | **Feature Area**: Voice Streaming / WebSocket

### Symptom
Sessions end prematurely with:
- `Audio Output: FAIL` in diagnostics
- `WebSocket closed: Server error — keepalive ping timeout` in connection log

### Root Cause
`main.py:/live` WebSocket handler sends no keepalive pings. Cloud Run's LB kills the connection during idle periods caused by Gemini reconnects or long function calls.

### Fix Applied
- Added `keepalive_ping()` async task in `main.py` — sends `{"type": "ping"}` every 15s
- Added client-side silent ping handler in `static/index.html`
- Ping task runs alongside send/receive, survives Gemini reconnects

### Dependencies
- Depends on #18 (session resumption + reconnect loop)
- Related to #15, #17

---

## Issue 2: Veo3 animation fails — empty response due to person_generation filter

**GitHub**: [#21](https://github.com/ithllc/FUSE/issues/21)
**Type**: Bug | **Severity**: Major | **Feature Area**: Visualization / Veo3

### Symptom
`GET /render/animate` returns error. Cloud Run logs: `Veo3 returned no videos. Operation: done=True error=None`.

### Root Cause
Imagen generates human-like silhouettes in architecture scenes. Veo3's `person_generation="dont_allow"` silently filters these out — returns `done=True` but empty `generated_videos`.

Secondary: `time.sleep()` in `async def animate()` blocks the event loop.

### Fix Applied
- Changed `person_generation` to `"allow_adult"` in `veo3_diagram_animator.py`
- Replaced `time.sleep()` with `await asyncio.sleep()` for non-blocking polling

---

## E2E Test Results (pre-deploy)

| Step | Status | Detail |
|------|--------|--------|
| Health check | PASS | All components OK |
| Vision frame (POST /vision/frame) | PASS | mermaid_length=18646 |
| Mermaid state (GET /state/mermaid) | PASS | Diagram confirmed |
| Validation (GET /validate) | PASS | is_valid=False, report_length=3386 |
| Imagen (GET /render/realistic) | PASS | 1.5MB PNG generated |
| Veo3 (GET /render/animate) | FAIL | Empty response (issue #21) |
