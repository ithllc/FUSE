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

### Connecting to the Live Session

1. Click **"Connect Live"** in the header bar — the status badge turns green ("Live")
2. Click **"Start Mic"** to enable voice input — a red pulsing indicator appears
3. Click **"Start Camera"** to enable video capture — the camera feed appears in the top-left panel

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

### API Endpoints for Diagrams

```bash
# Get current Mermaid code
curl http://localhost:8080/state/mermaid

# Render to PNG (returns image file)
curl http://localhost:8080/render --output diagram.png
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

### Automatic Frame Streaming

When the camera is active, frames are sent to the server at 2 FPS automatically. FUSE's VisionStateCapture component analyzes each frame for:
- Technical diagrams and sketches
- Whiteboard drawings with nodes and relationships
- Text labels and annotations

### Manual Frame Capture

Click **"Capture Frame"** to send a single high-quality frame for analysis. This triggers:
1. JPEG frame sent to `POST /vision/frame`
2. Gemini 3.1 Flash Lite extracts Mermaid.js code
3. Diagram panel updates with the extracted architecture
4. State is persisted to Redis

### API Endpoint

```bash
# Send a frame for analysis
curl -X POST http://localhost:8080/vision/frame \
  -H "Content-Type: application/octet-stream" \
  --data-binary @frame.jpg
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
