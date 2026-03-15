# PRD: Ephemeral Token Alternate Page for Direct Client-to-Gemini Live API

**Issue**: #30
**Status**: Draft
**Author**: FUSE Team
**Date**: 2026-03-14
**Hackathon Deadline**: 2026-03-16
**Priority**: P0 — Critical Path (demo stability)

---

## 1. Problem Statement

The current FUSE architecture proxies all audio through the FastAPI server to the Vertex AI Live API:

```
Browser → FastAPI WebSocket (/live) → Vertex AI Live API → FastAPI → Browser
```

This double-hop relay introduces:
- **Latency**: Audio traverses two WebSocket connections, adding 14-39ms server overhead per exchange
- **1007 errors**: Timing mismatches when audio frames arrive during session transitions
- **1008/1011 errors**: Race conditions when audio streams during pending tool calls
- **Session instability**: Complex reconnection logic with resumption handles that frequently fail
- **UnboundLocalError**: `_session_start_ts` crash after 5 responses (issue #29)

With the hackathon demo on March 16, we need a stable audio path that eliminates server-side audio proxying entirely.

## 2. Solution

Implement an **alternate FUSE page** that uses **Gemini API ephemeral tokens** for direct browser-to-Gemini WebSocket communication:

```
Browser → Gemini Live API WebSocket (direct, using ephemeral token)
Browser → FastAPI HTTP endpoints (vision, diagrams, validation — unchanged)
```

The server's only role for audio becomes generating a short-lived ephemeral token. All other FUSE features continue to use the existing FastAPI HTTP endpoints.

## 3. User Stories

| ID | Story | Acceptance Criteria |
|----|-------|-------------------|
| US-1 | As a FUSE user, I want to speak to Gemini and hear its response with minimal latency | Audio round-trip < 500ms (browser → Gemini → browser, no server hop) |
| US-2 | As a FUSE user, I want to see transcriptions of what I said and what Gemini said | Input and output transcriptions appear in the chat panel |
| US-3 | As a FUSE user, I want the pre-session diagnostics to verify audio and camera work | Diagnostics pass: audio output, mic input, camera — same flow as current page |
| US-4 | As a FUSE user, I want to use the vision pipeline to analyze whiteboard sketches | Camera frames sent via HTTP `/vision/frame` (unchanged) |
| US-5 | As a FUSE user, I want to see the System Status panel show component health | All components show green; Gemini Live shows "Gemini Live (using Ephemeral Tokens)" |
| US-6 | As a FUSE user, I want the session to auto-end after 5 minutes | Client-side session timer unchanged |
| US-7 | As a hackathon judge, I want to access the alternate page via a clear URL | `GET /ephemeral` serves the alternate page |

## 4. Technical Architecture

### 4.1 New Components

#### 4.1.1 Server: Ephemeral Token Endpoint

**File**: Additions to `main.py` (new route only, no modifications to existing code)

```
GET /api/ephemeral-token
```

- Uses `google-genai` SDK with `api_version='v1alpha'` to create an ephemeral token
- Requires `GEMINI_API_KEY` environment variable (Gemini Developer API key, NOT Vertex AI)
- Returns JSON: `{ "token": "<ephemeral_token_string>" }`
- Token configuration:
  - `uses`: 1 (single session)
  - `expire_time`: now + 30 minutes
  - `new_session_expire_time`: now + 2 minutes
- Locked configuration (optional, for security):
  - Model: `gemini-2.5-flash-native-audio`
  - `response_modalities`: `["AUDIO"]`

#### 4.1.2 Server: Alternate Page Route

**File**: Additions to `main.py` (new route only)

```
GET /ephemeral
```

- Serves `static/index_ephemeral_tokens.html`
- No authentication required (hackathon demo)

#### 4.1.3 Client: Alternate HTML Page

**File**: `static/index_ephemeral_tokens.html`

A copy of the existing `static/index.html` with these modifications:

1. **Title**: "FUSE - Collaborative Brainstorming Intelligence (Ephemeral Tokens)"
2. **WebSocket connection**: Instead of connecting to the server's `/live` WebSocket, the client:
   a. Fetches an ephemeral token from `GET /api/ephemeral-token`
   b. Opens a WebSocket directly to Gemini: `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained?access_token=<token>`
   c. Sends a setup message (`BidiGenerateContentSetup`) with model and config
   d. Streams audio directly to/from Gemini
3. **Audio handling**: Same PCM16 format (16kHz input, 24kHz output), but sent/received directly via the Gemini WebSocket
4. **Transcription**: Parsed from Gemini's `serverContent` messages (input_transcription, output_transcription fields)
5. **System Status**: Component health panel shows "Gemini Live (using Ephemeral Tokens)" instead of "Gemini Live"
6. **All HTTP features**: Vision, diagrams, validation, Imagen, Veo3 — unchanged, still use FastAPI endpoints

### 4.2 Gemini WebSocket Protocol

#### Connection
```
URL: wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained?access_token={token}
```

#### Setup Message (sent immediately after connection opens)
```json
{
  "setup": {
    "model": "models/gemini-2.5-flash-native-audio",
    "generationConfig": {
      "responseModalities": ["AUDIO"],
      "speechConfig": {
        "voiceConfig": {
          "prebuiltVoiceConfig": {
            "voiceName": "Puck"
          }
        }
      }
    },
    "systemInstruction": {
      "parts": [{ "text": "You are FUSE, an expert system architect..." }]
    },
    "realtimeInputConfig": {
      "automaticActivityDetection": {
        "startOfSpeechSensitivity": "START_SENSITIVITY_LOW",
        "endOfSpeechSensitivity": "END_SENSITIVITY_HIGH"
      }
    },
    "inputAudioTranscription": {},
    "outputAudioTranscription": {},
    "sessionResumption": {}
  }
}
```

#### Sending Audio
```json
{
  "realtimeInput": {
    "audio": {
      "data": "<base64-encoded PCM16 audio>",
      "mimeType": "audio/pcm;rate=16000"
    }
  }
}
```

#### Receiving Audio
Server sends messages with `serverContent.modelTurn.parts[].inlineData`:
```json
{
  "serverContent": {
    "modelTurn": {
      "parts": [{
        "inlineData": {
          "data": "<base64-encoded PCM16 audio>",
          "mimeType": "audio/pcm;rate=24000"
        }
      }]
    }
  }
}
```

#### Receiving Transcriptions
```json
{
  "serverContent": {
    "inputTranscription": { "text": "user said this" },
    "outputTranscription": { "text": "gemini said this" }
  }
}
```

### 4.3 Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Client)                      │
│                                                          │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │  Audio Pipeline       │  │  HTTP Features           │ │
│  │  ────────────────     │  │  ──────────────          │ │
│  │  Mic → PCM16 → WS    │  │  /vision/frame (POST)    │ │
│  │  WS → PCM16 → Speaker│  │  /health (GET)           │ │
│  │                       │  │  /render (GET)           │ │
│  │  Direct to Gemini     │  │  /validate (GET)         │ │
│  │  via ephemeral token  │  │  /state/mermaid (GET)    │ │
│  └───────────┬───────────┘  └───────────┬──────────────┘ │
│              │                           │                │
└──────────────┼───────────────────────────┼────────────────┘
               │                           │
               ▼                           ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│  Gemini Live API     │    │  FastAPI Server               │
│  (Google Cloud)      │    │  ──────────────               │
│  ──────────────      │    │  /api/ephemeral-token (NEW)   │
│  WebSocket direct    │    │  /ephemeral (NEW)             │
│  Audio streaming     │    │  /vision/frame                │
│  Transcription       │    │  /health, /healthz            │
│  Native audio model  │    │  /render, /validate           │
└──────────────────────┘    │  /state/mermaid               │
                            │  All existing routes...       │
                            └──────────────────────────────┘
```

### 4.4 Data Flow

1. **Page Load**: Browser loads `/ephemeral` → server returns `index_ephemeral_tokens.html`
2. **Splash Screen**: Health check via `/health` (same as current)
3. **Start Session**:
   a. Browser calls `GET /api/ephemeral-token`
   b. Server generates token via `genai.Client.auth_tokens.create()`
   c. Browser opens WebSocket to `wss://generativelanguage.googleapis.com/...?access_token={token}`
   d. Browser sends setup message with model config
   e. Gemini responds with `setupComplete`
4. **Audio Streaming**: Browser captures mic → PCM16 → base64 → JSON → Gemini WebSocket
5. **Audio Playback**: Gemini → base64 audio in serverContent → decode → play
6. **Vision/Diagrams**: Same HTTP flow as current page (no change)
7. **Session End**: Browser closes WebSocket, shows session overlay

## 5. Environment Requirements

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes (new) | Gemini Developer API key for ephemeral token generation |
| `PROJECT_ID` | No change | Still used for Vertex AI vision/pro/imagen/veo3 |
| `REDIS_HOST` | No change | Still used for state management |

## 6. File Inventory

| File | Type | Description |
|------|------|-------------|
| `static/index_ephemeral_tokens.html` | New | Alternate page with direct Gemini WebSocket |
| `docs/architecture/ephemeral_tokens/PRD_EPHEMERAL_TOKENS.md` | New | This document |
| `docs/architecture/ephemeral_tokens/TECHNICAL_PLAN.md` | New | Detailed implementation plan |
| `docs/architecture/ephemeral_tokens/ARCHITECTURE.md` | New | Architecture documentation |

Server-side additions (appended to `main.py` or as a separate router — TBD by technical plan):
- `GET /api/ephemeral-token` endpoint
- `GET /ephemeral` route

## 7. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `GEMINI_API_KEY` not set | Token endpoint fails | Return clear error message; fall back to original `/live` page |
| Ephemeral token expires mid-session | Audio drops | Client detects close, requests new token, reconnects |
| Gemini WebSocket protocol differs from Vertex AI | Audio format mismatch | Same PCM16 format confirmed in docs; test thoroughly |
| CORS/mixed content issues | WebSocket blocked | Gemini endpoint is HTTPS/WSS; no CORS for WebSocket |
| Rate limiting on token creation | Token endpoint throttled | Single-use tokens, 30-min lifetime reduces churn |

## 8. Out of Scope

- Modifying existing `static/index.html` or `main.py` WebSocket handler
- Server-side session management for ephemeral token sessions
- Multi-user authentication
- Function calling via ephemeral token (tool calls remain server-side via HTTP)
- Session resumption across page reloads (ephemeral token is single-use)

## 9. Success Metrics

- **Audio latency**: < 500ms browser-to-browser (vs current 14-39ms server overhead + Gemini processing)
- **Session stability**: 0 unplanned disconnects during 5-minute demo session
- **Zero 1007/1008 errors**: Direct connection eliminates server-side audio timing issues
- **Feature parity**: All FUSE features accessible (vision, diagrams, validation, visualization)
