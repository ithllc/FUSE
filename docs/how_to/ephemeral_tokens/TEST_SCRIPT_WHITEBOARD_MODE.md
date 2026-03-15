# Test Script: Whiteboard Mode (Ephemeral Tokens)

**Purpose**: End-to-end test of FUSE whiteboard/paper diagram capture using voice and vision.
**Duration**: ~5 minutes
**What you need**: A sheet of paper with a simple architecture sketch (boxes + arrows), or draw one during the session.

---

## Setup

1. Open https://fuse-service-864533297567.us-central1.run.app in Chrome
2. Wait for the splash page to show all 6 feature boxes and "Ready — Enter FUSE"
3. Click "Ready — Enter FUSE"
4. Wait for the component health panel to load (all components should show green except Redis locally)
5. Have your paper sketch ready (e.g., 3 boxes labeled "Client", "Server", "Database" with arrows)

---

## Step 1: Start Session

1. Click **Start Session** (button enables after components load)
2. Wait ~2 seconds for permission check (mic + camera)
3. Grant mic and camera permissions if prompted
4. Wait ~10 seconds — FUSE will greet you with audio (the model speaks first)
5. You'll see "Session active" in the Status Connection Log

---

## Step 2: Whiteboard Capture

1. Hold your paper sketch in front of the camera so it's clearly visible
2. Say: **"Can you look at what I'm holding up? It's a diagram on paper."**
3. Watch for in the chat panel:
   - `TOOL CALL: capture_and_analyze_frame({"mode":"whiteboard"})` — Gemini triggers vision capture
   - `TOOL RESULT: Vision capture (whiteboard)` — server processes the frame
4. Gemini will respond with audio describing what it sees in your diagram
5. If a Mermaid diagram is extracted, it renders automatically in the Architecture Diagram tab

---

## Step 3: Iterate on the Diagram

1. Say: **"Can you add a load balancer between the client and the server?"**
2. Gemini updates the architecture based on your request
3. If Mermaid code is generated, watch the workflow status area:
   - "Starting Design of Architectural Diagram..."
   - "Finished Design of Architectural Diagram"
   - "Starting Validation..."
   - "Finished Validation"
   - "Starting Image Generation for Visualization..."
   - etc.
4. Check the tabs: Architecture Diagram, Validation, Visualized Image, Animated Video

---

## Step 4: End Session

1. Click **End Session** or wait for the 5-minute auto-timeout
2. Session overlay appears with download and visualization options

---

## What to Watch For

- Gemini speaks first (~10s after session starts) — you don't need to speak first
- `TOOL CALL` messages appear in chat when Gemini triggers vision capture
- The workflow status area shows pipeline progress (no manual buttons needed)
- Architecture Diagram tab updates when Mermaid code is detected
- No 1007/1008 errors — direct ephemeral token connection is stable
