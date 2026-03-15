# How To Use FUSE

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Using the Web UI](#using-the-web-ui)
4. [Using the Python CLI Client](#using-the-python-cli-client)
5. [Working with Diagrams](#working-with-diagrams)
6. [Voice Interaction](#voice-interaction)
7. [Vision & Whiteboard Capture](#vision--whiteboard-capture)
8. [Proxy Object Registration (Imagine Mode)](#proxy-object-registration-imagine-mode)
9. [Architecture Validation](#architecture-validation)
10. [Accessing the Cloud Deployment](#accessing-the-cloud-deployment)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python 3.11+**
- **Node.js 20+** (for Mermaid CLI diagram rendering)
- **Google Cloud SDK** authenticated with a project that has Vertex AI enabled
- **Redis** instance (local or Google Cloud Memorystore)
- A modern browser with microphone and camera permissions (Chrome recommended)

### GCP Services Required

| Service | Purpose |
|---------|---------|
| Vertex AI | Gemini model access (Live API, Vision, Pro) |
| Cloud Memorystore (Redis) | Session state persistence |
| Cloud Run | Production deployment |
| Artifact Registry | Docker image storage |

---

## Local Development Setup

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/<your-org>/FUSE.git
cd FUSE
pip install -r requirements.txt
npm install -g @mermaid-js/mermaid-cli
```

### 2. Configure Environment Variables

Create a `.env` file in the project root:

```env
PROJECT_ID=your-gcp-project-id
LOCATION=global
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

> **Note:** The Live API model requires `us-central1` location. This is handled automatically in the code — the `LOCATION` variable is used for non-Live models only.

### 3. Start a Local Redis Instance

```bash
# Using Docker
docker run -d --name fuse-redis -p 6379:6379 redis:7-alpine

# Or install natively
redis-server
```

### 4. Start the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

The server initializes five components on startup:
1. **SessionStateManager** — connects to Redis
2. **ProofOrchestrator** — Gemini 3.1 Pro for validation
3. **VisionStateCapture** — Gemini 3.1 Flash Lite for whiteboard OCR
4. **GeminiLiveStreamHandler** — Gemini 2.5 Flash Native Audio for voice
5. **DiagramRenderer** — Mermaid CLI wrapper

### 5. Open the Web UI

Navigate to `http://localhost:8080` in your browser.

---

## Using the Web UI

The web UI is a four-panel interface:

```
+---------------------+---------------------+
|   Live Camera Feed  | Architecture Diagram|
|   (top-left)        |   (top-right)       |
+---------------------+---------------------+
|   Session Chat      | Validation Report   |
|   (bottom-left)     |   (bottom-right)    |
+---------------------+---------------------+
```

### Starting a Session

1. Wait for the splash page to show "Ready — Enter FUSE" (components are loading)
2. Click **"Ready — Enter FUSE"** to enter the main interface
3. Wait for the component health panel to show all components loaded
4. Click **"Start Session"** — the button enables after components load
5. Grant microphone and camera permissions when prompted (~2 second permission check)
6. Wait ~10 seconds — **FUSE greets you first** with audio (no need to speak first)
7. The status badge turns green ("Connected") and camera/mic activate automatically
8. Video streams to Gemini at 1 FPS for real-time visual awareness

### Voice Interaction

1. Simply speak naturally after FUSE greets you
2. FUSE responds with audio and transcripts appear in the chat panel
3. Gemini automatically calls functions when you reference visual content:
   - "Look at my whiteboard" → triggers `capture_and_analyze_frame(whiteboard)`
   - "The cup is our database" → triggers `set_proxy_object(cup, database)`
   - "What have we assigned?" → triggers `get_session_context()`

### Sending Text Messages

1. Type a message in the chat input field at the bottom-left
2. Click **"Send"** or press Enter
3. FUSE responds with audio (played through your speakers) and the transcript appears in chat

### Viewing Proxy Objects

1. Click the **"Proxy Objects"** tab in the chat panel
2. Registered proxy objects appear in a table showing Object ID and Technical Role

---

## Using the Python CLI Client

For headless environments or advanced usage:

```bash
# Connect to local server
python client_streamer.py --url http://localhost:8080 --fps 2

# Connect to Cloud Run deployment
python client_streamer.py --url https://fuse-service-864533297567.us-central1.run.app --fps 2
```

### Features

- **Webcam streaming** at configurable FPS (default: 2)
- **Microphone capture** via PyAudio (PCM16 @ 16kHz mono)
- **Fallback test frames** for WSL2/headless environments (auto-detected)
- **Audio response playback** from Gemini

### Optional Dependencies

```bash
pip install pyaudio  # For real microphone input (optional)
```

If PyAudio is not installed, the client sends silent audio frames as a fallback.

---

## Working with Diagrams

FUSE generates and renders Mermaid.js architecture diagrams in real-time.

### Automatic Diagram Generation

When you capture a whiteboard frame or describe architecture verbally, FUSE extracts entities and relationships into Mermaid.js syntax and renders the diagram in the top-right panel.

### Manual Diagram Actions

| Button | Action |
|--------|--------|
| **Refresh** | Fetches the latest Mermaid state from the server |
| **Render PNG** | Generates a server-side PNG using Mermaid CLI |
| **Visualize** | Generates a photorealistic image using Imagen 4.0 (10-30s) |
| **Animate** | Generates an animated walkthrough video using Veo 3.0 (30-120s) |

### Photorealistic Visualization (Imagen + Veo 3)

FUSE can transform your Mermaid architecture diagrams into photorealistic images and animated videos:

1. Click **"Visualize"** in the diagram panel header to generate a photorealistic CGI render of your architecture using Imagen 4.0
2. Click **"Animate"** to create a short cinematic walkthrough video using Veo 3.0 with data-flow effects
3. The realistic view panel shows the generated image/video with a toggle back to the standard diagram

These features are also accessible from the post-session overlay via **"Generate Demo"** > **"Image (Mockup)"** or **"Video (Animation)"**.

### API Endpoints for Diagrams

```bash
# Get current Mermaid code
curl http://localhost:8080/state/mermaid

# Render to PNG (returns image file)
curl http://localhost:8080/render --output diagram.png

# Generate photorealistic image (returns PNG)
curl http://localhost:8080/render/realistic --output realistic.png

# Generate animated walkthrough (returns MP4)
curl http://localhost:8080/render/animate --output walkthrough.mp4

# Full pipeline: image + video (returns JSON with base64)
curl http://localhost:8080/render/visualize
```

---

## Voice Interaction

FUSE uses the Gemini 2.5 Flash Native Audio model for real-time bidirectional voice conversation.

### How It Works

1. Browser captures microphone audio via Web Audio API (PCM16 @ 16kHz)
2. Audio frames are sent over WebSocket to the server
3. Server pipes audio directly to Gemini Live API
4. Gemini responds with audio bytes streamed back to the browser
5. Browser plays response audio at 24kHz

### Tips

- Speak clearly and describe the architecture you want to build
- Use commands like "Imagine this coffee mug is a database server" to register proxy objects
- Ask FUSE to validate your architecture: "Can you check this design for issues?"
- FUSE maintains context across the session — refer to previous statements naturally

---

## Vision & Whiteboard Capture

FUSE uses a **two-pass vision pipeline** for intelligent scene understanding:

1. **Pass 1 (Scene Classification)**: Classifies what the camera sees (whiteboard, objects, gesture, mixed, unclear) and returns a bounding box for the focal region
2. **ROI Cropping**: Crops the frame to the region of interest if confidence is sufficient
3. **Pass 2 (Mode-Specific Extraction)**: Uses a tailored prompt based on the scene type, injecting relevant session context (proxy registry, transcript, current diagram state)

### Vision Modes

Gemini automatically selects the appropriate vision mode based on your conversation context. The modes are:

| Mode | Behavior |
|------|----------|
| **Auto Detect** (default) | Pass 1 classifies the scene automatically |
| **Whiteboard** | Forces whiteboard extraction — ignores people and background |
| **Imagine (Objects)** | Forces proxy object recognition — uses proxy registry context |
| **Charades (Gestures)** | Forces gesture interpretation — uses voice transcript context |

You can also switch modes via text commands: type "whiteboard mode", "imagine mode", "charades mode", or "auto mode" in the chat input.

### Automatic Frame Streaming

When the camera is active, frames are sent to the server at 2 FPS automatically. Frames are debounced — if a previous frame is still being processed, new frames are skipped to prevent backlog.

### Manual Frame Capture

Click **"Capture Frame"** to send a single high-quality frame for analysis. This triggers:
1. JPEG frame sent to `POST /vision/frame`
2. Pass 1 classifies the scene and crops to ROI
3. Pass 2 extracts architecture using mode-specific prompt
4. Diagram panel updates with the extracted architecture
5. State is persisted to Redis

### Incremental Updates

The vision pipeline injects the current diagram state into every extraction prompt, instructing the model to update incrementally rather than regenerate from scratch. A merge heuristic prevents partial views from overwriting a complete diagram.

### API Endpoints

```bash
# Send a frame for analysis (auto mode)
curl -X POST http://localhost:8080/vision/frame \
  -H "Content-Type: application/octet-stream" \
  --data-binary @frame.jpg

# Send a frame with explicit mode override
curl -X POST "http://localhost:8080/vision/frame?mode=whiteboard" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @frame.jpg

# Get current vision mode
curl http://localhost:8080/vision/mode

# Set vision mode
curl -X POST http://localhost:8080/vision/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "imagine"}'
```

---

## Proxy Object Registration (Imagine Mode)

"Imagine Mode" lets you use everyday physical objects as stand-ins for technical components.

### How to Register a Proxy

1. Hold up an object to the camera
2. Say: "Imagine this [object] is a [technical component]"
   - Example: "Imagine this stapler is a GPU cluster"
   - Example: "Imagine this coffee mug is the primary database"

3. FUSE registers the mapping and tracks the object's spatial position

### Viewing Registered Proxies

- **Web UI:** Click the "Proxy Objects" tab in the chat panel
- **API:** Proxy data is stored in Redis under the session's `proxy_registry` hash

### Spatial Interaction

Move proxy objects around on your desk or whiteboard:
- "Move the GPU cluster closer to the load balancer"
- FUSE updates the architecture diagram to reflect spatial relationships

---

## Architecture Validation

FUSE periodically validates your architecture design using Gemini 3.1 Pro.

### Automatic Validation

A background task runs every 60 seconds, checking for:
- Network bottlenecks
- Single points of failure
- Logical inconsistencies
- Missing components

### Manual Validation

1. Click **"Run Validation"** in the bottom-right panel
2. The validation report displays with a green (valid) or red (issues found) indicator

### API Endpoint

```bash
curl http://localhost:8080/validate
# Returns: {"validation_report": "...", "is_valid": true/false}
```

---

## Accessing the Cloud Deployment

FUSE is deployed on Google Cloud Run at:

```
https://fuse-service-864533297567.us-central1.run.app
```

All features work identically to local development. The Cloud Run deployment includes:
- VPC connector for Redis access
- 1Gi memory allocation
- 300-second request timeout
- Session affinity for WebSocket stability

---

## System Status & Diagnostics

FUSE includes a built-in diagnostics panel for testing and demo debugging.

### Opening the System Status Panel

1. Click the **gear icon ("Status")** button in the header bar (next to "Start Session")
2. The panel expands below the header showing three sections:
   - **Components**: Green/red health indicators for Redis, Gemini Live, Gemini Vision, Gemini Pro, Diagram Renderer, Imagen 4.0, and Veo 3.0
   - **Session**: Current vision mode, proxy object count, diagram length, and recent event count
   - **Connection Log**: Timestamped, color-coded log of WebSocket connection stages, errors, and close codes

### Understanding Connection Errors

When a session fails, the Connection Log shows exactly where the failure occurred:

| Stage | Meaning |
|-------|---------|
| `initialization` | Live handler failed to start (server may still be booting) |
| `connecting` | WebSocket opened, now connecting to Gemini Live API |
| `connected` | Gemini session active, ready for voice/text |
| `gemini_connect` | Gemini Live API connection failed (check model access, region, permissions) |

### WebSocket Close Codes

| Code | Meaning |
|------|---------|
| 1000 | Normal closure (session ended intentionally) |
| 1006 | Abnormal closure (no close frame — network issue or server crash) |
| 1011 | Server error (handler not initialized or internal failure) |

### Health Check API

```bash
# Deep health check with component status and session summary
curl http://localhost:8080/health
```

Returns `"status": "ok"` when all components are healthy, or `"status": "degraded"` when any component is down. The `components` object shows per-component status, and the `session` object shows current state metrics and recent errors.

---

## Troubleshooting

### WebSocket Connection Fails

- Verify the server is running (`curl http://localhost:8080/health`)
- Check browser console for CORS or mixed-content errors
- For Cloud Run, ensure the URL uses `wss://` (not `ws://`)

### No Audio Response from FUSE

- Confirm the Live API model is accessible in `us-central1`
- Check that `response_modalities` is set to `["AUDIO"]` (not `["AUDIO", "TEXT"]`)
- Verify `api_version` is `v1beta1` in the client config

### Camera Not Working

- Grant camera permissions in the browser when prompted
- On WSL2/headless: use the Python client with `--url` flag (it generates test frames)

### Diagram Not Rendering

- Ensure Mermaid CLI is installed: `npx mmdc --version`
- Check that Puppeteer config exists: `puppeteer-config.json`
- For Docker: verify Chromium is installed and `PUPPETEER_EXECUTABLE_PATH` is set

### Redis Connection Errors

- Local: ensure Redis is running on the configured host/port
- Cloud Run: verify the VPC connector is attached and Memorystore is accessible

### Common Error Reference

See [docs/ERRORS_AND_FIXES.md](../ERRORS_AND_FIXES.md) for a comprehensive list of previously encountered errors and their resolutions.
