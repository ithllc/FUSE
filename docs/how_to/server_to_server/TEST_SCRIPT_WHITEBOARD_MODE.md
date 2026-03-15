# Test Script: Whiteboard Mode

**Purpose**: End-to-end test of FUSE using a physical whiteboard or paper sketch.
**Duration**: ~5 minutes
**What you need**: A whiteboard/paper with drawn boxes and arrows, or draw them during the session.

---

## Setup

1. Open https://fuse-service-864533297567.us-central1.run.app in Chrome
2. Wait for the splash page countdown to finish
3. Have a whiteboard or paper ready with a simple architecture sketch (or be ready to draw one)
   - Example sketch: 3 boxes labeled "Client", "Server", "Database" with arrows between them

---

## Phase 1: Pre-Session Diagnostics

**What happens**: The system tests your microphone, camera, and audio output.

1. Click **"Start Session"**
   - _Expected_: Button turns red, says "End Session"
   - _Expected_: Camera and microphone activate automatically
   - _Expected_: Connection log shows "WebSocket connected"

2. Wait for the **3-2-1 countdown** in the chat
   - _Expected_: "Microphone test starting in 3..."
   - _Expected_: Connection log shows "DIAG: Countdown starting — 3..."

3. When prompted, say: **"Hello FUSE"**
   - _Expected_: Connection log shows "DIAG: Microphone input PASS"
   - _Expected_: You hear FUSE respond with a greeting
   - _Expected_: Connection log shows "DIAG: Audio output PASS"

4. Camera test runs automatically
   - _Expected_: Connection log shows "DIAG: Camera PASS — frame sent successfully"

5. All diagnostics pass
   - _Expected_: "All diagnostics passed. Starting session."
   - _Expected_: Connection log shows "Session active"
   - _Expected_: Session timer starts (5-minute countdown in header)

**Troubleshooting**:
- If microphone doesn't pass: speak louder, check browser mic permissions
- If audio output doesn't pass: check volume, wait for FUSE to speak
- If camera doesn't pass: check browser camera permissions, ensure good lighting

---

## Phase 2: Gemini Live API Conversation (Whiteboard Mode)

**Goal**: Get FUSE to see and describe your whiteboard, then extract it as a diagram.

6. Set the vision mode — say or select from dropdown:
   > **"Switch to whiteboard mode"**
   - _Expected_: FUSE responds: "Switched to whiteboard mode"
   - _Expected_: Vision mode dropdown updates to "Whiteboard"

7. Point your camera at the whiteboard and say:
   > **"Hey FUSE, can you see the whiteboard? Describe what you see on it."**
   - _Expected_: Connection log shows "TOOL: capture_and_analyze_frame ✓" (function call)
   - _Expected_: FUSE describes the whiteboard contents via audio
   - _Expected_: Example response: "I can see a whiteboard with three boxes labeled Client, Server, and Database connected by arrows..."

8. Ask FUSE to confirm the architecture:
   > **"That's right. The client connects to the server via REST API, and the server reads from the database. Can you capture that as a diagram?"**
   - _Expected_: FUSE acknowledges and the vision pipeline processes the frame
   - _Expected_: Diagram panel (top-right) updates with Mermaid diagram
   - _Expected_: You see boxes and arrows matching your whiteboard sketch

9. Ask for modifications:
   > **"Add a load balancer between the client and the server"**
   - _Expected_: FUSE acknowledges the change
   - _Expected_: Diagram may update on next frame capture

10. Ask FUSE about the current state:
    > **"What does the current architecture look like?"**
    - _Expected_: Connection log shows "TOOL: get_session_context ✓"
    - _Expected_: FUSE describes the current diagram from Redis state

---

## Phase 3: Architecture Validation

11. Click **"Run Validation"** button in the bottom-right panel
    - _Expected_: Validation report appears with green (valid) or red (issues) indicator
    - _Expected_: Report mentions components like Client, Server, Database

12. Or ask verbally:
    > **"Can you validate this architecture? Are there any single points of failure?"**
    - _Expected_: FUSE discusses potential issues (e.g., "The server is a single point of failure — consider adding redundancy")

---

## Phase 4: Visualization (Imagen)

13. Click **"Visualize"** button in the diagram panel header
    - _Expected_: Loading indicator appears (10-30 seconds)
    - _Expected_: A photorealistic CGI rendering of your architecture appears
    - _Expected_: Components are represented as visual metaphors (gateway arches, vaults, etc.)

14. Toggle between diagram and realistic view using the view toggle

---

## Phase 5: Animation (Veo 3)

15. Click **"Animate"** button in the diagram panel header
    - _Expected_: Loading indicator appears (30-120 seconds — Veo 3 generation is slow)
    - _Expected_: A short animated walkthrough video plays showing data flow through the architecture

---

## Phase 6: End Session

16. Click **"End Session"**
    - _Expected_: Connection log shows "WebSocket closed: Normal closure"
    - _Expected_: Post-session overlay appears with session summary
    - _Expected_: Options to generate demo image/video are available

---

## What to Check in the Connection Log

| Entry | Meaning |
|-------|---------|
| `DIAG: Microphone input PASS` | Mic working |
| `DIAG: Audio output PASS` | Speakers working |
| `DIAG: Camera PASS` | Camera working |
| `Session active` | Diagnostics complete, session started |
| `TOOL: capture_and_analyze_frame ✓ (XXXms)` | Vision function call succeeded |
| `TOOL: get_session_context ✓ (XXXms)` | Context retrieval succeeded |
| `Audio session reconnected` | Gemini session auto-reconnected (issue #18) |
| `Session resumption handle updated` | Resumption token captured |
| `WebSocket closed: Normal closure` | Clean session end (code 1000) |
