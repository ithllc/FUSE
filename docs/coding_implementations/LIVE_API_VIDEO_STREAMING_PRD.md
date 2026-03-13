# PRD: Gemini Live API Audio+Video Streaming

**Status**: Planned
**Priority**: P0 — Hackathon Critical
**Target**: Gemini Live Agent Challenge (deadline March 16, 2026)

---

## 1. Product Identity

**Feature Name**: Gemini Live API Audio+Video Streaming

**Elevator Pitch**: Send real-time camera frames alongside audio to the Gemini Live API so FUSE's AI brainstorming partner can see what the user is showing — whiteboards, physical objects, hand gestures — and respond with full visual context instead of being blind.

**Problem Statement**: Currently, the Gemini Live API session is audio-only. When a user holds up a stapler and says "this is a load balancer," Gemini cannot see the stapler. It must rely on an explicit function call (`capture_and_analyze_frame`) to get a single snapshot. This creates a disjointed experience where:
- Gemini cannot understand spatial references ("this," "that," "over here")
- Proxy object assignments require the user to over-describe what they're holding
- Whiteboard content is invisible until explicitly captured
- Charades gestures are meaningless without visual context
- The AI feels like a voice assistant, not a collaborative brainstorming partner

**Existing Product Addition**: This extends the existing `/live` WebSocket handler and `GeminiLiveStreamHandler` component.

---

## 2. Audience & Scope

**Target Users**: Brainstorming session participants using the FUSE web UI with camera and microphone enabled.

**Platforms**: Chrome browser (primary), any WebRTC-capable browser.

**In Scope**:
- Sending JPEG frames to Gemini Live API via `send_realtime_input(video=...)`
- Maintaining audio streaming alongside video
- SlidingWindow compression to handle the 2-minute token limit for audio+video
- Connection log observability for video streaming state
- Component health check for video streaming
- Cloud Run structured logging for video events

**Out of Scope**:
- Changing the REST `/vision/frame` pipeline (it continues running in parallel unchanged)
- Changing the Gemini model (stays `gemini-live-2.5-flash-native-audio`)
- Client-side video encoding/transcoding (browser provides JPEG via canvas)
- Recording or persisting video frames server-side

**Deployment Model**: Cloud Run (existing infrastructure, no changes)

---

## 3. Feature Pillars

### Pillar 1: Real-Time Visual Awareness
Gemini Live API receives camera frames at 1 FPS so it can see what the user sees. This enables:
- Understanding deictic references ("this stapler," "that whiteboard")
- Observing object placement and spatial relationships
- Detecting hand gestures and body positioning
- Reading whiteboard content as it's being written

### Pillar 2: Dual Pipeline Architecture
Two parallel vision streams serve different purposes:

| Pipeline | Purpose | Rate | Model |
|----------|---------|------|-------|
| **Live API Video** | Real-time awareness — Gemini sees and understands context | 1 FPS | `gemini-live-2.5-flash-native-audio` |
| **REST /vision/frame** | Heavy extraction — two-pass scene classification, ROI cropping, Mermaid generation with session notes + proxy context | 1 FPS | `gemini-3.1-flash-lite-preview` |

Both streams receive the same frames. The Live API gives Gemini awareness; the REST pipeline does detailed extraction.

### Pillar 3: Session Stability with Compression
Audio+video at 283 tokens/second fills the 128K context window in ~7.5 minutes. SlidingWindow compression (already implemented in issue #18) discards old context — including old frames — keeping the session alive indefinitely. Old frames are irrelevant anyway, making this an ideal use case for sliding window.

### Pillar 4: Observability
Every aspect of video streaming is visible to the user and logged for debugging:
- Connection log shows "VIDEO: Streaming at 1 FPS" during active sessions
- Connection log shows frame send failures
- `/health` endpoint reports video streaming state
- Cloud Run logs structured video events (frame count, errors, latency)

---

## 4. User Stories

### US-1: Real-Time Object Recognition
> As a brainstorming participant, I want Gemini to see the objects I'm holding up so it can correctly identify proxy objects (stapler=load balancer, mug=database) without me having to describe them in detail.

**Acceptance Criteria**:
- User holds up a stapler and says "this is a load balancer"
- Gemini sees the stapler via video input and responds with "I can see you're holding a stapler — I'll register it as the load balancer"
- `set_proxy_object` function call fires with correct object name

### US-2: Whiteboard Awareness
> As a brainstorming participant, I want Gemini to see my whiteboard in real-time so it can describe what's drawn and proactively suggest capturing the architecture.

**Acceptance Criteria**:
- User points camera at whiteboard with boxes and arrows
- Without being asked, Gemini says "I can see a diagram on the whiteboard with three components..."
- User says "capture that as a diagram" and the function call fires at the right moment

### US-3: Gesture Interpretation
> As a brainstorming participant using Charades mode, I want Gemini to see my hand gestures so it can correlate my physical movements with my verbal description of the topology.

**Acceptance Criteria**:
- User makes a star-burst gesture and says "this is a star topology"
- Gemini sees the gesture AND hears the description
- Gemini responds: "I can see you're showing a star pattern — a central hub with nodes radiating outward"

### US-4: Session Duration
> As a brainstorming participant, I want my session to last the full 5-minute timer even with video streaming enabled.

**Acceptance Criteria**:
- Session with audio+video runs for full 5 minutes without disconnection
- SlidingWindow compression keeps the context window below 128K tokens
- If Gemini reconnects (GoAway), video streaming resumes automatically

### US-5: Observability
> As a developer or demo presenter, I want to see that video streaming is working in the connection log so I can troubleshoot issues during a live demo.

**Acceptance Criteria**:
- Connection log shows "VIDEO: Streaming started (1 FPS, 768x768)"
- Connection log shows frame count periodically: "VIDEO: 30 frames sent"
- Connection log shows errors: "VIDEO: Frame send failed — [reason]"
- Video streaming state reported via WebSocket `video_status` messages (removed from `/health` — video is part of Gemini Live API component, issue #24)

---

## 5. Technical Constraints

| Constraint | Value |
|-----------|-------|
| **Max FPS** | 1 FPS (Gemini Live API limit) |
| **Optimal resolution** | 768x768 pixels |
| **JPEG quality** | 70-75 |
| **Token rate (video)** | 258 tokens/second |
| **Token rate (audio+video)** | 283 tokens/second |
| **Context window** | 128K tokens |
| **Session duration (no compression)** | ~2 minutes |
| **Session duration (with SlidingWindow)** | Unlimited |
| **send_realtime_input constraint** | Only ONE parameter per call (audio and video must be separate calls) |
| **Supported formats** | JPEG (`image/jpeg`), PNG (`image/png`) |
| **Model** | `gemini-live-2.5-flash-native-audio` (unchanged) |

---

## 6. Success Metrics

| Metric | Target |
|--------|--------|
| Video frames delivered to Gemini per session | ≥ 250 (5 min × 1 FPS - overhead) |
| Session survival rate with video | ≥ 95% (no premature disconnection) |
| Gemini visual reference accuracy | Gemini correctly identifies shown objects in ≥ 80% of cases |
| Latency: frame capture to Gemini acknowledgment | < 2 seconds |
| Connection log video entries visible | 100% of sessions show VIDEO status |
| Health check includes video state | Yes |

---

## 7. Dependencies

| Dependency | Status |
|-----------|--------|
| SlidingWindow compression (issue #18) | Implemented |
| Session resumption + reconnect loop (issue #18) | Implemented |
| WebSocket keepalive ping (issue #20) | Implemented |
| Function calling tools (issue #19) | Implemented |
| REST /vision/frame two-pass pipeline | Implemented |

---

## 8. Handoff

- Run `/technical-plan` to generate the phased implementation plan from this PRD
- Run `/project` to ingest as kanban tasks
