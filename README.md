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
- **Real-Time Voice Conversation** — Bidirectional voice streaming with Gemini 2.5 Flash Native Audio for natural, hands-free interaction
- **"Imagine" Mode** — Use everyday objects (coffee mug, stapler, notebook) as physical proxies for technical components. Say "Imagine this mug is a database" and FUSE tracks it in the architecture
- **Automated Architecture Validation** — Gemini 3.1 Pro continuously checks designs for bottlenecks, single points of failure, and logical inconsistencies
- **Live Diagram Rendering** — Mermaid.js diagrams rendered in real-time as the architecture evolves

---

## Architecture

```
Browser / Python Client
    │
    ├── WebSocket /live ──────────► Gemini Live API (Voice)
    │                                 gemini-2.5-flash-native-audio
    │
    ├── POST /vision/frame ───────► VisionStateCapture
    │                                 gemini-3.1-flash-lite-preview
    │
    └── GET /validate ────────────► ProofOrchestrator
                                     gemini-3.1-pro-preview
                                          │
                                     Redis (State)
                                          │
                                     DiagramRenderer
                                       (Mermaid CLI)
```

### Component Overview

| Component | Model | Purpose |
|-----------|-------|---------|
| GeminiLiveStreamHandler | `gemini-2.5-flash-native-audio` | Bidirectional voice streaming |
| VisionStateCapture | `gemini-3.1-flash-lite-preview` | Whiteboard OCR and diagram extraction |
| ProofOrchestrator | `gemini-3.1-pro-preview` | Architecture validation and reasoning |
| SessionStateManager | — | Redis-backed session persistence |
| DiagramRenderer | — | Mermaid CLI to PNG conversion |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **AI Models** | Google Gemini (Vertex AI) — 3 specialized models |
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
| `/` | GET | Web UI |
| `/live` | WebSocket | Bidirectional voice/vision streaming |
| `/vision/frame` | POST | Submit camera frame for analysis |
| `/state/mermaid` | GET | Current architecture state (Mermaid code) |
| `/render` | GET | Render architecture to PNG |
| `/validate` | GET | Run architecture validation |
| `/command` | POST | Submit text command |
| `/health` | GET | Health check |

---

## Project Structure

```
FUSE/
├── main.py                          # FastAPI server and endpoints
├── client_streamer.py               # Python CLI client (webcam + mic)
├── static/index.html                # Web UI
├── src/
│   ├── audio/
│   │   └── gemini_live_stream_handler.py   # Gemini Live API voice streaming
│   ├── vision/
│   │   └── vision_state_capture.py         # Whiteboard frame analysis
│   ├── state/
│   │   └── session_state_manager.py        # Redis session persistence
│   ├── agents/
│   │   └── proof_orchestrator.py           # Architecture validation
│   └── output/
│       └── diagram_renderer.py             # Mermaid CLI rendering
├── tests/
│   ├── test_vision_state.py
│   └── test_audio_proxy.py
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
- **[Errors & Fixes](docs/ERRORS_AND_FIXES.md)** — Resolved issues and lessons learned

---

## Demonstration

### Web UI

The four-panel interface provides simultaneous access to:

| Panel | Function |
|-------|----------|
| **Top-Left** | Live camera feed with frame capture |
| **Top-Right** | Real-time Mermaid.js architecture diagram |
| **Bottom-Left** | Chat transcript + proxy object registry |
| **Bottom-Right** | Architecture validation reports |

### Voice Interaction

1. Click **Connect Live** to establish the WebSocket session
2. Click **Start Mic** to begin voice streaming
3. Speak naturally — FUSE responds with audio and updates diagrams in real time

### Imagine Mode

Hold a physical object to the camera and say:
> "Imagine this coffee mug is the primary database server."

FUSE registers the proxy object and tracks it in the architecture diagram.

---

## Google Cloud Services Used

- **Vertex AI** — Gemini model hosting and inference
- **Cloud Run** — Serverless container deployment
- **Cloud Memorystore** — Managed Redis for session state
- **Artifact Registry** — Docker image storage
- **Cloud Build** — CI/CD pipeline
- **Serverless VPC Access** — Network connectivity between Cloud Run and Memorystore

---

## License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

See [LICENSE](LICENSE) for the full license text.
