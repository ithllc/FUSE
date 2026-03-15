# Architecture: Ephemeral Token Direct Audio Connection

**Issue**: #30
**Date**: 2026-03-14

---

## Overview

The ephemeral token architecture provides a direct browser-to-Gemini audio path that bypasses the server-side WebSocket proxy. This eliminates the double-hop relay that caused 1007/1008 WebSocket errors in the original architecture.

## Architecture Comparison

### Original Architecture (Server-Proxied)
```
┌──────────┐    WebSocket /live    ┌──────────────┐    Vertex AI SDK    ┌──────────────┐
│  Browser  │ ──────────────────── │  FastAPI      │ ────────────────── │  Gemini Live │
│           │ ◄─────────────────── │  Server       │ ◄────────────────── │  API         │
│  (PCM16   │    binary audio      │  (proxy)      │    audio bytes     │  (Vertex AI) │
│   binary) │    + JSON text       │              │    + SDK objects    │              │
└──────────┘                       └──────────────┘                     └──────────────┘
```

**Issues**: 1007 errors from timing mismatches, 1008 from tool call races, complex session management, `_session_start_ts` crashes.

### Ephemeral Token Architecture (Direct)
```
┌──────────────────┐
│     Browser       │
│                   │         JSON (base64 audio)
│  Audio Pipeline   │ ─────────────────────────────────┐
│  Mic → PCM16     │                                   │
│  → base64 → JSON │                                   ▼
│                   │                          ┌──────────────────┐
│  JSON → base64   │                          │  Gemini Live API │
│  → PCM16 → Spkr  │ ◄────────────────────── │  (Google Cloud)  │
│                   │    JSON (base64 audio)   │  Direct WebSocket│
│  HTTP Features    │                          └──────────────────┘
│  ─────────────    │
│  /vision/frame ──────┐
│  /health       ──────┤
│  /render       ──────┤    HTTP REST
│  /validate     ──────┤
│  /api/ephemeral ─────┤
│     -token      ─────┘
└──────────────────┘    │
                        ▼
              ┌──────────────────┐
              │  FastAPI Server   │
              │  (unchanged)      │
              │                   │
              │  Vision pipeline  │
              │  State management │
              │  Diagram rendering│
              │  Token generation │
              └──────────────────┘
```

## Data Flow

### Session Lifecycle

```
1. Page Load
   Browser ──GET /ephemeral──▶ FastAPI ──▶ index_ephemeral_tokens.html
   Browser ──GET /health────▶ FastAPI ──▶ Component status JSON

2. Session Start
   Browser ──GET /api/ephemeral-token──▶ FastAPI
   FastAPI ──auth_tokens.create()──────▶ Gemini API (v1alpha)
   FastAPI ◄── { token: "..." } ───────── Gemini API
   Browser ◄── { status: ok, token } ──── FastAPI

3. WebSocket Connection
   Browser ──WSS + access_token──▶ Gemini Live API
   Browser ──JSON setup message──▶ Gemini Live API
   Browser ◄── setupComplete ────── Gemini Live API

4. Audio Streaming (bidirectional)
   Browser ──{ realtimeInput: { audio: { data: base64 } } }──▶ Gemini
   Browser ◄── { serverContent: { modelTurn: { parts: [{ inlineData: { data: base64 } }] } } }

5. Transcriptions
   Browser ◄── { serverContent: { inputTranscription: { text: "..." } } }
   Browser ◄── { serverContent: { outputTranscription: { text: "..." } } }

6. Vision (HTTP, unchanged)
   Browser ──POST /vision/frame──▶ FastAPI ──▶ VisionStateCapture
```

## Component Interaction Matrix

| Feature | Original Path | Ephemeral Token Path |
|---------|--------------|---------------------|
| Audio streaming | Browser → FastAPI WS → Vertex AI → FastAPI WS → Browser | Browser → Gemini WS → Browser |
| Transcription | Gemini → SDK → FastAPI → WS JSON → Browser | Gemini → WS JSON → Browser |
| Function calling | Gemini → SDK → FastAPI (execute) → SDK → Gemini | Gemini → Browser WS (execute stub/HTTP) → Browser WS → Gemini |
| Vision analysis | Browser → HTTP POST → FastAPI → Gemini Flash | **Same** (called from browser on tool call) |
| Diagram rendering | Browser → HTTP GET → FastAPI → Mermaid CLI | **Same** |
| Architecture validation | Browser → HTTP GET → FastAPI → Gemini Pro | **Same** |
| Imagen visualization | Browser → HTTP GET → FastAPI → Imagen 4.0 | **Same** |
| Veo3 animation | Browser → HTTP GET → FastAPI → Veo 3.0 | **Same** |
| System health | Browser → HTTP GET → FastAPI → ping components | **Same** |
| Token generation | N/A | Browser → HTTP GET → FastAPI → Gemini API |
| Session events | Server logs directly (WebSocket lifecycle) | Browser → POST /api/session-event → Server logs |
| Tool call events | Server logs directly (tool execution) | Browser → POST /api/tool-event → Server logs |

## Security Model

### Token Lifecycle
```
Server (trusted)                        Client (untrusted)
────────────────                        ──────────────────
GEMINI_API_KEY (env var)
      │
      ▼
genai.Client(api_key=KEY)
      │
      ▼
auth_tokens.create(
  uses=1,
  expire=30min,
  new_session=2min
)
      │
      ▼
ephemeral token ─────────────────────▶ token (short-lived)
                                              │
                                              ▼
                                       WSS connection with
                                       ?access_token=...
                                              │
                                              ▼
                                       Single session only
                                       Expires in 30 min
```

- The `GEMINI_API_KEY` never leaves the server
- Ephemeral tokens are single-use and time-limited
- Token can optionally be locked to specific model/config (not implemented for hackathon)

## Audio Format Specification

| Direction | Format | Sample Rate | Encoding | Channel |
|-----------|--------|-------------|----------|---------|
| Input (mic → Gemini) | PCM16 | 16,000 Hz | 16-bit signed LE, base64 | Mono |
| Output (Gemini → speakers) | PCM16 | 24,000 Hz | 16-bit signed LE, base64 | Mono |

### Client-Side Audio Pipeline

```
Microphone
    │
    ▼
getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } })
    │
    ▼
AudioContext (may run at 48kHz)
    │
    ▼
ScriptProcessorNode (bufferSize: 512)
    │
    ▼
Float32 samples → downsample if needed → Int16 PCM
    │
    ▼
Uint8Array → String.fromCharCode loop → btoa() = base64
    │
    ▼
JSON: { realtimeInput: { audio: { data: base64, mimeType: "audio/pcm;rate=16000" } } }
    │
    ▼
ws.send(JSON.stringify(...))
```

```
Gemini response
    │
    ▼
JSON: { serverContent: { modelTurn: { parts: [{ inlineData: { data: base64 } }] } } }
    │
    ▼
atob(base64) → Uint8Array → ArrayBuffer
    │
    ▼
Int16Array → Float32Array (divide by 32768)
    │
    ▼
AudioContext(24000Hz) → AudioBuffer → BufferSource → speakers
```

## Function Calling (Client-Side)

The ephemeral token page handles Gemini's tool calls entirely in the browser:

```
Gemini sends toolCall message (binary JSON frame)
    │
    ▼
Browser ws.onmessage decodes binary → JSON
    │
    ▼
For each functionCall in toolCall.functionCalls:
    ├── capture_and_analyze_frame(mode) → stub (local) / POST /vision/frame (production)
    ├── get_session_context() → stub (local) / GET /state/mermaid (production)
    └── set_proxy_object(name, role) → updates local proxyRegistry / POST /command (production)
    │
    ▼
Browser sends toolResponse JSON back to Gemini via WebSocket
    │
    ▼
Browser fires POST /api/tool-event to server (fire-and-forget, for Cloud Logging)
```

### Registered Functions

| Function | Description | Stub Behavior | Production Behavior |
|----------|-------------|--------------|-------------------|
| `capture_and_analyze_frame` | Vision capture + analysis | Returns mock scene data | `POST /vision/frame?mode=X` |
| `get_session_context` | Current session state | Returns local proxyRegistry | `GET /state/mermaid` + `GET /health` |
| `set_proxy_object` | Register object→component mapping | Updates local proxyRegistry | `POST /command?text=...` |

## Observability

### Structured Logging (Cloud Run → Cloud Logging)

All structured logs use `EVENT=` prefix for Cloud Logging filterability:

| Event | Trigger | Key Fields |
|-------|---------|-----------|
| `ephemeral_page_served` | `GET /ephemeral` | client_ip, user_agent |
| `ephemeral_token_created` | `GET /api/ephemeral-token` (success) | token_prefix, client_ip |
| `ephemeral_token_failed` | `GET /api/ephemeral-token` (error) | error, client_ip |
| `ephemeral_session_connect` | Browser: setupComplete received | client_ip |
| `ephemeral_session_active` | Browser: diagnostics complete | client_ip, detail |
| `ephemeral_session_disconnect` | Browser: WebSocket closed | client_ip, duration_seconds, audio_chunks_sent/received, latency_avg_ms |
| `ephemeral_session_error` | Browser: WebSocket error | client_ip, detail |
| `ephemeral_tool_call` | Browser: function call completed | function, args, status, latency_ms, call_id, client_ip |
| `vision_frame_processed` | `POST /vision/frame` complete | outcome, duration_ms, frame_size, mermaid_length |

### Cloud Logging Queries

```
# All ephemeral events
textPayload:"EVENT=ephemeral_"

# Token audit trail
textPayload:"EVENT=ephemeral_token_created"

# Session lifecycle
textPayload:"EVENT=ephemeral_session_disconnect"

# Function calling
textPayload:"EVENT=ephemeral_tool_call"
textPayload:"function=capture_and_analyze_frame"

# Vision performance
textPayload:"EVENT=vision_frame_processed"
```

## File Inventory

| File | Purpose | New/Modified |
|------|---------|-------------|
| `main.py` | Token endpoint, page route, session/tool event logging (appended) | Modified (append only) |
| `static/index_ephemeral_tokens.html` | Direct Gemini audio page with function calling + event reporting | New |
| `static/system_instructions_ephemeral_tokens.md` | Saved system instructions for reimplementation | New |
| `docs/architecture/ephemeral_tokens/PRD_EPHEMERAL_TOKENS.md` | Product requirements | New |
| `docs/architecture/ephemeral_tokens/PRD_CLOUD_LOGGING.md` | Cloud logging PRD | New |
| `docs/architecture/ephemeral_tokens/PRD_TOOL_EVENT_LOGGING.md` | Tool event logging PRD | New |
| `docs/architecture/ephemeral_tokens/TECHNICAL_PLAN.md` | Implementation plan | New |
| `docs/architecture/ephemeral_tokens/TECHNICAL_PLAN_LOGGING.md` | Logging implementation plan | New |
| `docs/architecture/ephemeral_tokens/TECHNICAL_PLAN_TOOL_LOGGING.md` | Tool logging implementation plan | New |
| `docs/architecture/ephemeral_tokens/ARCHITECTURE.md` | This document | New |
