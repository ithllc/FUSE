# Test Script: Charades Mode (Ephemeral Tokens)

**Purpose**: End-to-end test of FUSE using hand gestures and body positioning to describe architecture topologies.
**Duration**: ~5 minutes
**What you need**: Your hands and enough space for the camera to see your upper body/hands clearly.

---

## Setup

1. Open https://fuse-service-864533297567.us-central1.run.app in Chrome
2. Click "Ready — Enter FUSE" after the splash page loads
3. Wait for components to load, then click **Start Session**
4. Grant mic and camera permissions if prompted
5. Wait for FUSE to greet you (~10 seconds)
6. Position yourself so the camera can see your hands and upper body

---

## Step 1: Introduce Charades

1. Say: **"I'm going to act something out for you. Watch my gestures and tell me what you see."**
2. Gemini acknowledges and watches via the video stream

---

## Step 2: Gesture a Topology

1. Use your hands to mime a layered architecture:
   - Hold one hand high (top layer — "client")
   - Hold another hand in the middle ("server")
   - Point down ("database")
   - Move your hands to show data flowing between layers
2. Say: **"What did you see me doing?"**
3. Watch for:
   - `TOOL CALL: capture_and_analyze_frame({"mode":"charades"})` — Gemini analyzes your gestures
4. Gemini describes what it observed

---

## Step 3: Refine with Voice

1. Say: **"That's right — I was showing a three-tier architecture. Can you draw that as a diagram?"**
2. Gemini generates a Mermaid diagram based on the combined gesture + voice context
3. Architecture Diagram tab updates automatically
4. Workflow status shows pipeline progress

---

## Step 4: Combine with Proxy Objects

1. Pick up an object (e.g., a book)
2. Say: **"This book represents the caching layer. Place it between the client and server tiers."**
3. Watch for:
   - `TOOL CALL: set_proxy_object({"object_name":"book","technical_role":"caching layer"})`
4. Gemini incorporates the cache into the architecture

---

## What to Watch For

- Gemini speaks first — no need for you to initiate
- Gemini automatically selects "charades" mode when you mention gestures or acting things out
- The model can see your gestures through the video stream (video-to-Gemini is ON by default)
- No manual mode switching needed — Gemini picks the right mode from conversation context
- Gesture + voice combined provides richer architectural context than either alone
