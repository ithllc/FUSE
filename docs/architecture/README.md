# FUSE Architecture Overview

FUSE supports two architecture approaches for connecting to the Gemini Live API. Both use the same Gemini models, session state management (Redis), and vision pipeline. They differ only in how audio streams flow between the browser and Gemini.

---

## Server-to-Server (Vertex AI)

```
Browser (mic/speaker) <--WebSocket--> FastAPI Server <--Live API--> Vertex AI (Gemini)
                                          |
                                    Redis / Vision / Imagen / Veo3
```

**Flow:** The browser captures audio and sends it via WebSocket to the FastAPI server. The server proxies audio to the Vertex AI Live API, receives Gemini's audio responses, and relays them back to the browser over the same WebSocket.

**Characteristics:**
- All audio traffic passes through the server (higher latency, higher bandwidth cost).
- Server maintains the Live API session lifecycle.
- Full IAM and VPC controls -- the browser never talks directly to Google APIs.
- Supports audit logging, rate limiting, and content filtering at the server layer.
- Currently experiences 1007/1008 WebSocket disconnection issues under certain conditions.

**When to use:**
- Enterprise deployments requiring IAM access controls and VPC security.
- Environments where browsers cannot make direct external WebSocket connections.
- Use cases requiring server-side audio processing, filtering, or recording.
- Compliance scenarios where all API traffic must pass through a controlled gateway.

**Documentation:** See `server_to_server/` subdirectory.

---

## Ephemeral Tokens (Direct)

```
Browser (mic/speaker) <--WebSocket--> Gemini Live API (direct)
         |
         +--HTTP--> FastAPI Server (token generation, vision, state, rendering)
```

**Flow:** The server generates a short-lived ephemeral token via the Gemini API. The browser uses this token to establish a direct WebSocket connection to the Gemini Live API. Audio streams flow directly between the browser and Gemini without passing through the server. The server handles only HTTP endpoints: token generation, vision frame analysis, session state, and rendering.

**Characteristics:**
- Audio latency is minimized (no server proxy hop).
- Server bandwidth reduced significantly (no audio relay).
- Zero 1007/1008 WebSocket disconnection errors (browser manages its own connection).
- Production-ready and stable.
- Browser must be able to connect directly to Google APIs.

**When to use:**
- Production deployments prioritizing low latency and reliability.
- Hackathon demos and public-facing applications.
- Scenarios where the browser has direct internet access.
- Default recommended approach for most use cases.

**Documentation:** See `ephemeral_tokens/` subdirectory.

---

## Shared Components (Both Approaches)

Both architectures share these server-side components:

- **SessionStateManager** (`src/state/`): Redis-backed session state with proof orchestration.
- **VisionStateCapture** (`src/vision/`): Two-pass vision pipeline (scene classification + mode-specific extraction).
- **Imagen/Veo3 Visualization** (`src/output/`): Diagram-to-image and diagram-to-video rendering.
- **Mermaid State Machine** (`src/state/`): Architecture state tracking and diagram generation.
- **Static UI** (`static/`): `index.html` (server-to-server) and `index_ephemeral_tokens.html` (ephemeral tokens).
