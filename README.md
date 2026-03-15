# FUSE — Collaborative Brainstorming Intelligence

**Real-time, vision-and-voice AI agent for high-stakes technical brainstorming sessions.**

FUSE transforms messy human interactions — whiteboard sketches, hand gestures, spoken ideas, and physical object placement — into structured, validated system architecture diagrams, all in real time.

[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Deployed-4285F4?logo=google-cloud)](https://cloud.google.com)
[![Gemini](https://img.shields.io/badge/Powered%20by-Gemini%20AI-8E75B2)](https://ai.google.dev)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

---

## Team #AlwaysLateToEverything

**Team Members:** Frank Ivey, Jeti Olaf

**Hackathon:** [Gemini Live Agent Challenge](https://devpost.com) — Live Agents Category

---

## What It Does

FUSE is a multimodal AI brainstorming partner that sees, hears, and collaborates with you in real time. Point your camera at a whiteboard, speak your ideas, and watch as FUSE builds and validates architecture diagrams on the fly.

### Key Capabilities

- **Live Whiteboard Extraction** — Camera captures whiteboard sketches and FUSE converts them into structured Mermaid.js diagrams using Gemini 3.1 Flash Lite
- **Real-Time Voice + Video Conversation** — Bidirectional audio+video streaming with Gemini 2.5 Flash Native Audio. Gemini sees camera frames at 1 FPS for real-time visual awareness of whiteboards, objects, and gestures
- **"Imagine" Mode** — Use everyday objects (coffee mug, stapler, notebook) as physical proxies for technical components. Say "Imagine this mug is a database" and FUSE tracks it in the architecture
- **"Charades" Mode** — Use hand gestures and body positioning to describe architecture topologies while narrating verbally
- **Automated Architecture Validation** — Gemini 3.1 Pro continuously checks designs for bottlenecks, single points of failure, and logical inconsistencies
- **Live Diagram Rendering** — Mermaid.js diagrams rendered in real-time as the architecture evolves
- **Photorealistic Visualization** — Imagen 4.0 transforms Mermaid diagrams into photorealistic CGI renders of infrastructure
- **Animated Walkthroughs** — Veo 3.0 generates cinematic data-flow animations from the realistic images
- **Auto-Workflow** — After a diagram is created, FUSE automatically validates, visualizes, and animates — each output appears in its own tab as it completes

---

## Architecture

FUSE supports two architecture modes. The **Ephemeral Token** mode is the production default.

### Ephemeral Token Mode (Production — `/ephemeral`)

Direct browser-to-Gemini audio/video via ephemeral tokens. Zero server-side audio relay.

```
Browser
    │
    ├── WSS (direct) ─────────────► Gemini Live API (Audio + Video + Function Calling)
    │     ephemeral token auth        gemini-2.5-flash-native-audio-latest
    │     audio PCM + video JPEG      Handles: capture_and_analyze_frame,
    │     + function calling            get_session_context, set_proxy_object
    │
    ├── GET /api/ephemeral-token ─► FastAPI ──► Gemini API (token generation)
    │                                            GEMINI_API_KEY via Secret Manager
    │
    ├── POST /vision/frame ───────► VisionStateCapture (Two-Pass Pipeline)
    │     (JPEG, 0.5 FPS)            gemini-3.1-flash-lite-preview
    │
    ├── GET /validate ────────────► ProofOrchestrator
    │                                 gemini-3.1-pro-preview
    │
    ├── GET /render/realistic ────► ImagenDiagramVisualizer
    │                                 imagen-4.0-generate-001
    │
    └── GET /render/animate ──────► Veo3DiagramAnimator
                                     veo-3.0-generate-preview
                                          │
                                     Redis (State)
                                          │
                                     DiagramRenderer
                                       (Mermaid CLI)
```

### Server-to-Server Mode (Legacy — `/`)

Server proxies audio between browser and Vertex AI. Used for enterprise deployments with IAM controls.

```
Browser
    │
    ├── WebSocket /live ──────────► FastAPI ──► Vertex AI Live API
    │     (binary audio PCM)          gemini-live-2.5-flash-native-audio
    │
    └── (same HTTP endpoints as above)
```

See [docs/architecture/README.md](docs/architecture/README.md) for detailed comparison.

### Component Overview

| Component | Model | Purpose |
|-----------|-------|---------|
| GeminiLiveStreamHandler | `gemini-2.5-flash-native-audio` | Bidirectional audio+video streaming with function calling |
| VisionStateCapture | `gemini-3.1-flash-lite-preview` | Two-pass whiteboard/object/gesture extraction |
| ProofOrchestrator | `gemini-3.1-pro-preview` | Architecture validation and reasoning |
| SessionStateManager | — | Redis-backed session persistence |
| DiagramRenderer | — | Mermaid CLI to PNG conversion |
| ImagenDiagramVisualizer | `imagen-4.0-generate-001` | Photorealistic architecture image generation |
| Veo3DiagramAnimator | `veo-3.0-generate-preview` | Animated data-flow walkthrough videos |
| MermaidSceneTranslator | — | Mermaid AST to visual scene description (70+ mappings) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **AI Models** | Google Gemini (Vertex AI) — 5 specialized models + Imagen 4.0 + Veo 3.0 |
| **State** | Google Cloud Memorystore (Redis) |
| **Diagrams** | Mermaid.js + mermaid-cli (Node.js) |
| **Deployment** | Google Cloud Run, Artifact Registry, Cloud Build |
| **Frontend** | Single-page web UI (HTML/CSS/JS) with WebSocket streaming |
| **SDK** | Google GenAI SDK (`google-genai`) |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Google Cloud SDK (authenticated)
- GCP project with Vertex AI API enabled

### Setup

```bash
# Clone the repository
git clone https://github.com/<your-org>/FUSE.git
cd FUSE

# Install Python dependencies
pip install -r requirements.txt

# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Start Redis (Docker)
docker run -d --name fuse-redis -p 6379:6379 redis:7-alpine

# Configure environment
cp .env.example .env
# Edit .env with your GCP project ID

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8080
```

Open `http://localhost:8080` in Chrome.

### Cloud Deployment

FUSE deploys to Google Cloud Run via Cloud Build:

```bash
gcloud builds submit --config cloudbuild.yaml
```

The build pipeline:
1. Builds the Docker image with all dependencies (Python, Node.js, Chromium, Mermaid CLI)
2. Pushes to Artifact Registry
3. Deploys to Cloud Run with VPC connector for Redis access

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI (server-to-server mode) |
| `/ephemeral` | GET | Web UI (ephemeral token mode — production) |
| `/api/ephemeral-token` | GET | Generate ephemeral token for direct Gemini connection |
| `/api/session-event` | POST | Client-side session lifecycle events for Cloud Logging |
| `/api/tool-event` | POST | Client-side tool call telemetry for Cloud Logging |
| `/live` | WebSocket | Server-proxied audio+video streaming (legacy mode) |
| `/vision/frame` | POST | Submit camera frame for analysis (supports `?mode=` override) |
| `/vision/mode` | GET/POST | Get or set vision mode (`auto`, `whiteboard`, `imagine`, `charades`) |
| `/state/mermaid` | GET | Current architecture state (Mermaid code) |
| `/render` | GET | Render architecture to PNG |
| `/render/realistic` | GET | Generate photorealistic image via Imagen 4.0 |
| `/render/animate` | GET | Generate animated walkthrough via Veo 3.0 |
| `/render/visualize` | GET | Full pipeline: image + video (returns base64 JSON) |
| `/validate` | GET | Run architecture validation via Gemini 3.1 Pro |
| `/command` | POST | Submit text command |
| `/health` | GET | Deep health check with component status |
| `/healthz` | GET | Lightweight liveness probe |

---

## Project Structure

```
FUSE/
├── main.py                          # FastAPI server and endpoints
├── client_streamer.py               # Python CLI client (webcam + mic)
├── static/index.html                # Web UI (server-to-server mode)
├── static/index_ephemeral_tokens.html  # Web UI (ephemeral token mode — production)
├── src/
│   ├── audio/
│   │   └── gemini_live_stream_handler.py   # Gemini Live API audio+video streaming
│   ├── vision/
│   │   └── vision_state_capture.py         # Whiteboard frame analysis
│   ├── state/
│   │   └── session_state_manager.py        # Redis session persistence
│   ├── agents/
│   │   └── proof_orchestrator.py           # Architecture validation
│   └── output/
│       ├── diagram_renderer.py             # Mermaid CLI rendering
│       ├── imagen_diagram_visualizer.py    # Photorealistic image generation (Imagen 4.0)
│       ├── veo3_diagram_animator.py        # Animated walkthrough generation (Veo 3.0)
│       └── mermaid_scene_translator.py     # Mermaid AST to visual scene descriptions
├── tests/
│   ├── test_vision_state.py
│   ├── test_audio_proxy.py
│   ├── generate_hrm_test_image.py          # Generates test image with 6 architecture shapes
│   └── test_vision_pipeline_e2e.py         # E2E test: frame → diagram → validate → visualize → animate
├── docs/
│   ├── how_to/                      # Usage guides
│   ├── architecture/                # System design documentation
│   ├── coding_implementations/      # PRD and technical specs
│   └── ERRORS_AND_FIXES.md
├── Dockerfile
├── cloudbuild.yaml
├── requirements.txt
└── puppeteer-config.json
```

---

## Documentation

- **[How To Use FUSE](docs/how_to/HOW_TO_USE_FUSE.md)** — Complete usage guide for the web UI and CLI client
- **[System Overview](docs/architecture/SYSTEM_OVERVIEW.md)** — Architecture diagrams and component roles
- **[State Management](docs/architecture/STATE_MANAGEMENT.md)** — Redis schema and session lifecycle
- **[Multimodal Workflows](docs/architecture/MULTIMODAL_WORKFLOWS.md)** — Vision, voice, and rendering pipelines
- **[Product Requirements](docs/coding_implementations/FUSE_PRD.md)** — Feature pillars and success metrics
- **[Technical Guide](docs/coding_implementations/FUSE_TECHNICAL_INSTALLATION_GUIDE.md)** — Phase-by-phase implementation
- **[Imagen/Veo3 Visualization](docs/coding_implementations/IMAGEN_VEO3_DIAGRAM_VISUALIZATION.md)** — Photorealistic rendering and animation pipeline
- **[UX Workflow Analysis](docs/UX_WORKFLOW_ANALYSIS.md)** — Auto-workflow design and tab progression
- **[Errors & Fixes](docs/ERRORS_AND_FIXES.md)** — Resolved issues and lessons learned

---

## Demonstration

### Web UI
[![FUSE Interface](/docs/submission/FUSE-UI-V3.png)]([target-url](https://fuse-service-864533297567.us-central1.run.app/))

The four-panel interface provides simultaneous access to:

| Panel | Function |
|-------|----------|
| **Top-Left** | Live camera feed with vision mode selector and frame capture |
| **Bottom-Left** | Chat transcript + proxy object registry |
| **Right** | Architecture output with 4 tabs: Diagram, Validation, Visualized Image, Animated Video |

The right panel tabs activate progressively as the auto-workflow completes each step — providing real-time visibility into system processing.

### Voice Interaction

1. Click **Start Session** to connect and run pre-session diagnostics (mic, audio, camera)
2. After diagnostics pass, speak naturally — FUSE responds with audio and updates diagrams in real time
3. As diagrams are created, the system auto-validates, generates a photorealistic image, and creates an animated walkthrough — each appearing in its own tab

### Imagine Mode

Hold a physical object to the camera and say:
> "Imagine this coffee mug is the primary database server."

FUSE registers the proxy object and tracks it in the architecture diagram.

---

## Automated Testing

FUSE includes an E2E test suite for the vision pipeline:

```bash
# Generate a test image with 6 architecture shapes
python tests/generate_hrm_test_image.py

# Run the full pipeline test against Cloud Run (or local)
python tests/test_vision_pipeline_e2e.py

# Override target URL for local testing
FUSE_URL=http://localhost:8080 python tests/test_vision_pipeline_e2e.py
```

The test sends a shapes-only image through: `POST /vision/frame` → `GET /state/mermaid` → `GET /validate` → `GET /render/realistic` → `GET /render/animate`, saving all outputs to `tests/outputs/`.

---

## Google Cloud Services Used

- **Vertex AI** — Gemini model hosting and inference (vision, validation, Imagen, Veo3)
- **Gemini Developer API** — Ephemeral token generation for direct Live API access
- **Cloud Run** — Serverless container deployment
- **Cloud Memorystore** — Managed Redis for session state
- **Secret Manager** — Secure storage for GEMINI_API_KEY
- **Artifact Registry** — Docker image storage
- **Cloud Build** — CI/CD pipeline
- **Serverless VPC Access** — Network connectivity between Cloud Run and Memorystore

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

See [LICENSE](LICENSE) for the full license text.
