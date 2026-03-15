# Technical Implementation Plan: Ephemeral Token Alternate Page

**Issue**: #30
**PRD**: `docs/architecture/ephemeral_tokens/PRD_EPHEMERAL_TOKENS.md`
**Date**: 2026-03-14
**Deadline**: 2026-03-16

---

## Overview

This plan implements a direct browser-to-Gemini audio connection using ephemeral tokens, eliminating the server-side audio proxy that causes 1007/1008 errors. The implementation adds two server-side routes and one new HTML page — **zero modifications to existing files**.

## Architecture Decision Record

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Token generation | Server-side Python endpoint | API key must stay server-side for security |
| WebSocket connection | Client-side JavaScript, direct to Gemini | Eliminates double-hop latency and server-side session bugs |
| Audio format | Same PCM16 (16kHz in, 24kHz out) | Gemini Live API uses identical format regardless of Vertex AI or Developer API |
| Protocol version | `v1alpha` | Required for ephemeral tokens (per Google docs) |
| Setup message | Raw JSON via WebSocket | No SDK on client side; raw WebSocket protocol is well-documented |
| Existing features | HTTP endpoints unchanged | Vision, diagrams, Imagen, Veo3 all use REST, not WebSocket |

---

## Phase 1: Server-Side Ephemeral Token Endpoint

### Objective
Add `GET /api/ephemeral-token` and `GET /ephemeral` routes to `main.py` without modifying any existing code.

### Implementation

#### 1.1 Token Endpoint Code

Add these routes **after** all existing routes in `main.py` (before `run_periodic_validation`):

```python
# --- Ephemeral Token Alternate Page (Issue #30) ---

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

@app.get("/ephemeral", response_class=HTMLResponse)
async def serve_ephemeral_ui():
    """Serves the ephemeral token alternate page."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index_ephemeral_tokens.html")
    if not os.path.exists(html_path):
        return HTMLResponse(content="<h1>Ephemeral token page not found</h1>", status_code=404)
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/ephemeral-token")
async def create_ephemeral_token():
    """Generates a short-lived ephemeral token for direct Gemini Live API access.

    Requires GEMINI_API_KEY environment variable (Gemini Developer API key).
    Token is valid for 1 session, expires in 30 minutes.
    """
    if not GEMINI_API_KEY:
        return {"status": "error", "message": "GEMINI_API_KEY not configured on server."}

    try:
        import datetime
        from google import genai

        client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options={"api_version": "v1alpha"}
        )

        now = datetime.datetime.now(tz=datetime.timezone.utc)

        token = client.auth_tokens.create(
            config={
                "uses": 1,
                "expire_time": now + datetime.timedelta(minutes=30),
                "new_session_expire_time": now + datetime.timedelta(minutes=2),
                "http_options": {"api_version": "v1alpha"},
            }
        )

        return {
            "status": "ok",
            "token": token.name,
            "expires_in_seconds": 1800,
            "model": "gemini-2.5-flash-native-audio",
        }
    except Exception as e:
        logger.error(f"Ephemeral token creation failed: {e}")
        return {"status": "error", "message": str(e)}
```

#### 1.2 Health Check Update for Alternate Page

The existing `/health` endpoint checks `live_handler` for Gemini Live status. The ephemeral page will call `/health` but interpret the response differently client-side — showing "Gemini Live (using Ephemeral Tokens)" based on whether `/api/ephemeral-token` returns successfully, not based on the server's `live_handler`.

**No server-side health changes needed** — the client-side JavaScript handles the display label.

### Files
| File | Action | Lines Added |
|------|--------|-------------|
| `main.py` | Append routes (no existing code changes) | ~40 |

### Dependencies
- `GEMINI_API_KEY` env var must be set
- `google-genai` SDK already installed (used by existing handlers)

---

## Phase 2: Client-Side HTML Page

### Objective
Create `static/index_ephemeral_tokens.html` — a copy of `index.html` with the WebSocket connection replaced by direct Gemini connection via ephemeral token.

### 2.1 Changes from Original `index.html`

The alternate page is a modified copy with these specific differences:

#### 2.1.1 Title and Branding
```html
<!-- Original -->
<title>FUSE - Collaborative Brainstorming Intelligence</title>
<span>Collaborative Brainstorming Intelligence</span>
<div class="splash-powered">Powered by Gemini 2.5 Flash · Vertex AI · Cloud Run</div>

<!-- Ephemeral Token Version -->
<title>FUSE - Collaborative Brainstorming Intelligence (Ephemeral Tokens)</title>
<span>Collaborative Brainstorming Intelligence (Direct Audio)</span>
<div class="splash-powered">Powered by Gemini 2.5 Flash Native Audio · Ephemeral Tokens · Cloud Run</div>
```

#### 2.1.2 WebSocket URL Removed
```javascript
// REMOVED — no server WebSocket for audio
// const WS_URL = BASE.replace('http://', 'ws://').replace('https://', 'wss://') + '/live';

// NEW — Gemini WebSocket constants
const GEMINI_WS_BASE = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained';
const GEMINI_MODEL = 'models/gemini-2.5-flash-native-audio';
```

#### 2.1.3 Connection Flow Replacement

**Original** (`connectWebSocket()` in `index.html` — line 1045):
```javascript
function connectWebSocket() {
    ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => { /* diagnostics start */ };
    ws.onmessage = (event) => { /* parse server JSON or binary audio */ };
    ws.onclose = (event) => { /* cleanup */ };
}
```

**Ephemeral Token Version** — replaces the entire `connectWebSocket()`:
```javascript
async function connectWebSocket() {
    addMsg('system', 'Requesting ephemeral token...');
    addConnectionLog('Fetching ephemeral token from server...', 'info');

    try {
        // Step 1: Get ephemeral token from our server
        const tokenResp = await fetch(BASE + '/api/ephemeral-token');
        const tokenData = await tokenResp.json();

        if (tokenData.status !== 'ok' || !tokenData.token) {
            addMsg('system', 'Failed to get token: ' + (tokenData.message || 'Unknown error'));
            addConnectionLog('Token error: ' + (tokenData.message || 'Unknown error'), 'error');
            return;
        }

        addConnectionLog('Token received. Connecting to Gemini...', 'ok');

        // Step 2: Connect directly to Gemini Live API
        const wsUrl = GEMINI_WS_BASE + '?access_token=' + encodeURIComponent(tokenData.token);
        ws = new WebSocket(wsUrl);

        let setupComplete = false;

        ws.onopen = () => {
            addConnectionLog('WebSocket connected to Gemini. Sending setup...', 'ok');

            // Step 3: Send setup message
            const setupMsg = {
                setup: {
                    model: GEMINI_MODEL,
                    generationConfig: {
                        responseModalities: ['AUDIO'],
                        speechConfig: {
                            voiceConfig: {
                                prebuiltVoiceConfig: {
                                    voiceName: 'Puck'
                                }
                            }
                        }
                    },
                    systemInstruction: {
                        parts: [{
                            text: 'You are FUSE, an expert system architect and brainstorming facilitator. '
                                + 'You help users design complex systems using voice and vision. '
                                + 'Keep your responses concise. '
                                + 'When the session begins, greet the user and ask them to say a few words '
                                + 'to test their microphone.'
                        }]
                    },
                    realtimeInputConfig: {
                        automaticActivityDetection: {
                            startOfSpeechSensitivity: 'START_SENSITIVITY_LOW',
                            endOfSpeechSensitivity: 'END_SENSITIVITY_HIGH'
                        }
                    },
                    inputAudioTranscription: {},
                    outputAudioTranscription: {},
                    sessionResumption: {}
                }
            };

            ws.send(JSON.stringify(setupMsg));
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                // Handle setupComplete
                if (msg.setupComplete) {
                    setupComplete = true;
                    sessionState = 'diagnostics';
                    setStatus(true);
                    addConnectionLog('Gemini setup complete', 'ok');
                    addMsg('system', 'Connected to Gemini. Preparing diagnostics...');
                    document.getElementById('btnConnect').textContent = 'End Session';
                    document.getElementById('btnConnect').style.background = '#da3633';
                    document.getElementById('btnConnect').style.borderColor = '#f85149';

                    fetchVisionMode();
                    if (!cameraStream) toggleCamera();
                    if (!micActive) toggleMic();

                    diagChecks = { audioOutput: false, micInput: false, camera: false };
                    diagAudioChunks = 0;
                    diagLastAudioTime = 0;
                    diagFirstBurstDone = false;

                    setTimeout(runCameraDiagnostic, 2000);
                    runDiagCountdown();
                    return;
                }

                // Handle serverContent (audio + transcriptions)
                if (msg.serverContent) {
                    const sc = msg.serverContent;

                    // Input transcription (user speech)
                    if (sc.inputTranscription && sc.inputTranscription.text) {
                        addMsg('user', sc.inputTranscription.text);
                        if (sessionState === 'diagnostics' && !diagChecks.micInput
                            && sc.inputTranscription.text.trim()) {
                            diagChecks.micInput = true;
                            addConnectionLog('DIAG: Microphone input PASS — speech transcribed: "'
                                + sc.inputTranscription.text.substring(0, 40) + '"', 'ok');
                            addMsg('system', 'Diagnostic: Microphone working. Your speech was detected.');
                            checkDiagComplete();
                        }
                    }

                    // Output transcription (Gemini speech)
                    if (sc.outputTranscription && sc.outputTranscription.text) {
                        addMsg('fuse', sc.outputTranscription.text);
                        checkForMermaid(sc.outputTranscription.text);
                    }

                    // Audio data in model turn
                    if (sc.modelTurn && sc.modelTurn.parts) {
                        for (const part of sc.modelTurn.parts) {
                            if (part.inlineData && part.inlineData.data) {
                                // Decode base64 to ArrayBuffer
                                const binaryStr = atob(part.inlineData.data);
                                const bytes = new Uint8Array(binaryStr.length);
                                for (let i = 0; i < binaryStr.length; i++) {
                                    bytes[i] = binaryStr.charCodeAt(i);
                                }
                                playAudioResponse(bytes.buffer);

                                // Latency instrumentation
                                latencyAudioResponseCount++;
                                if (latencyExchangeOpen && latencyLastMicSendTs > 0) {
                                    const rtt = Math.round(performance.now() - latencyLastMicSendTs);
                                    latencyClientSamples.push(rtt);
                                    if (latencyClientSamples.length > 50) latencyClientSamples.shift();
                                    latencyExchangeOpen = false;
                                    if (latencyAudioResponseCount <= 3 || latencyAudioResponseCount % 10 === 0) {
                                        const avg = Math.round(latencyClientSamples.reduce((a,b) => a+b, 0) / latencyClientSamples.length);
                                        addConnectionLog('LATENCY #' + latencyAudioResponseCount + ': browser→gemini→browser ' + rtt + 'ms (avg ' + avg + 'ms, n=' + latencyClientSamples.length + ')', 'info');
                                    }
                                }

                                // Diagnostic: audio output working
                                if (sessionState === 'diagnostics' && !diagChecks.audioOutput) {
                                    diagChecks.audioOutput = true;
                                    addConnectionLog('DIAG: Audio output PASS — receiving audio from Gemini', 'ok');
                                    addMsg('system', 'Diagnostic: Audio output working. FUSE is responding.');
                                    checkDiagComplete();
                                }
                            }

                            // Text parts (if model sends text alongside audio)
                            if (part.text) {
                                addMsg('fuse', part.text);
                                checkForMermaid(part.text);
                            }
                        }
                    }
                }

                // Handle session resumption update
                if (msg.sessionResumptionUpdate) {
                    addConnectionLog('Session resumption handle updated', 'info');
                }

                // Handle goAway
                if (msg.goAway) {
                    addConnectionLog('Gemini GoAway received. Session will end soon.', 'error');
                    addMsg('system', 'Gemini session ending. Please start a new session.');
                }

            } catch (e) {
                console.error('Error parsing Gemini message:', e, event.data);
            }
        };

        ws.onclose = (event) => {
            // Same cleanup as original — reuse existing onclose logic
            const wasActive = sessionState === 'active' || sessionState === 'diagnostics' || sessionState === 'ending';
            const reason = event.reason || 'No reason provided';
            const codeMap = {
                1000: 'Normal closure',
                1001: 'Going away',
                1006: 'Abnormal closure (no close frame)',
                1008: 'Policy violation',
                1011: 'Server error',
            };
            const codeDesc = codeMap[event.code] || ('Code ' + event.code);
            addConnectionLog('Gemini WebSocket closed: ' + codeDesc + ' — ' + reason, event.code === 1000 ? 'ok' : 'error');
            addMsg('system', 'Disconnected: ' + codeDesc);

            ws = null;
            setStatus(false);
            clearSessionTimer();
            if (diagTimer) { clearTimeout(diagTimer); diagTimer = null; }
            if (videoFrameInterval) { clearInterval(videoFrameInterval); videoFrameInterval = null; }
            document.getElementById('btnConnect').textContent = 'Start Session';
            document.getElementById('btnConnect').style.background = '';
            document.getElementById('btnConnect').style.borderColor = '';
            document.getElementById('btnConnect').disabled = false;
            if (micActive) toggleMic();
            if (cameraStream) toggleCamera();
            if (wasActive) {
                sessionState = 'ended';
                showSessionOverlay();
            } else {
                sessionState = 'idle';
            }
        };

        ws.onerror = (e) => {
            addConnectionLog('Gemini WebSocket error', 'error');
            addMsg('system', 'WebSocket connection error. Check browser console.');
        };

    } catch (e) {
        addMsg('system', 'Connection failed: ' + e.message);
        addConnectionLog('Connection failed: ' + e.message, 'error');
    }
}
```

#### 2.1.4 Audio Sending — PCM16 to Base64 JSON

**Original** (`micProcessor.onaudioprocess` in `index.html` — line 1297):
```javascript
// Original: send raw binary PCM16 to server WebSocket
ws.send(pcm16.buffer);
```

**Ephemeral Token Version** — sends base64-encoded JSON:
```javascript
micProcessor.onaudioprocess = (e) => {
    if (!micActive || !ws || ws.readyState !== WebSocket.OPEN) return;

    let float32 = e.inputBuffer.getChannelData(0);

    // Downsample if browser is not actually running at 16kHz
    const actualRate = audioContext.sampleRate;
    if (actualRate !== SAMPLE_RATE) {
        float32 = downsampleBuffer(float32, actualRate, SAMPLE_RATE);
    }

    // Convert Float32 [-1,1] to Int16 PCM
    const pcm16 = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    // Encode as base64 for Gemini JSON protocol
    const uint8 = new Uint8Array(pcm16.buffer);
    let binary = '';
    for (let i = 0; i < uint8.length; i++) {
        binary += String.fromCharCode(uint8[i]);
    }
    const b64 = btoa(binary);

    // Send as Gemini realtimeInput message
    ws.send(JSON.stringify({
        realtimeInput: {
            audio: {
                data: b64,
                mimeType: 'audio/pcm;rate=16000'
            }
        }
    }));

    // Latency instrumentation
    latencyLastMicSendTs = performance.now();
    if (!latencyExchangeOpen) latencyExchangeOpen = true;
};
```

#### 2.1.5 Text Input via WebSocket

**Original** (line 1543):
```javascript
ws.send(JSON.stringify({ text: text }));
```

**Ephemeral Token Version**:
```javascript
// Send text as realtimeInput (Gemini protocol)
ws.send(JSON.stringify({
    realtimeInput: {
        text: text
    }
}));
```

#### 2.1.6 System Status — Component Name Override

**Original** `renderComponentHealth()` (line 2019):
```javascript
const names = {
    redis: 'Redis', gemini_live: 'Gemini Live', gemini_vision: 'Gemini Vision',
    gemini_pro: 'Gemini Pro', diagram_renderer: 'Diagram Renderer',
    imagen: 'Imagen 4.0', veo3: 'Veo 3.0'
};
```

**Ephemeral Token Version**:
```javascript
const names = {
    redis: 'Redis', gemini_live: 'Gemini Live (using Ephemeral Tokens)',
    gemini_vision: 'Gemini Vision',
    gemini_pro: 'Gemini Pro', diagram_renderer: 'Diagram Renderer',
    imagen: 'Imagen 4.0', veo3: 'Veo 3.0'
};
```

#### 2.1.7 Removed Features (Server-Proxied Only)

The following features are **removed** from the ephemeral token page because they depend on the server-side WebSocket proxy:

1. **Video-to-Gemini A/B toggle** — Video frames were sent through the server WebSocket. Vision is still available via HTTP `/vision/frame`.
2. **Server-side latency instrumentation** — No server hop means no `data.type === 'latency'` messages. Client-side latency still measured.
3. **Keepalive pings from server** — No server WebSocket means no `data.type === 'ping'` messages.
4. **Video toggle acknowledgment** — No `data.type === 'video_toggle_ack'` messages.
5. **Video status messages** — No `data.type === 'video_status'` messages.
6. **Tool call activity** — No `data.type === 'tool_activity'` messages (function calling not available via ephemeral tokens).
7. **Status/error messages from server** — No `data.type === 'status'` or `data.type === 'error'` messages.
8. **Command results** — No `data.type === 'command_result'` messages.

All these `ws.onmessage` handlers for server-specific message types are **removed**. The `ws.onmessage` handler only processes Gemini protocol messages.

#### 2.1.8 Video Frame Streaming to Gemini via WebSocket

Since the ephemeral token WebSocket connects directly to Gemini, video frames can optionally be sent as `realtimeInput.video`:

```javascript
function sendVideoFrameWS() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const video = document.getElementById('localVideo');
    if (!video || !video.videoWidth) return;
    const canvas = document.getElementById('captureCanvas');
    canvas.width = 768;
    canvas.height = 768;
    const ctx = canvas.getContext('2d');
    const vw = video.videoWidth, vh = video.videoHeight;
    const side = Math.min(vw, vh);
    const sx = (vw - side) / 2, sy = (vh - side) / 2;
    ctx.drawImage(video, sx, sy, side, side, 0, 0, 768, 768);
    canvas.toBlob((blob) => {
        if (!blob || !ws || ws.readyState !== WebSocket.OPEN) return;
        blob.arrayBuffer().then(buf => {
            const uint8 = new Uint8Array(buf);
            let binary = '';
            for (let i = 0; i < uint8.length; i++) {
                binary += String.fromCharCode(uint8[i]);
            }
            const b64 = btoa(binary);
            ws.send(JSON.stringify({
                realtimeInput: {
                    video: {
                        data: b64,
                        mimeType: 'image/jpeg'
                    }
                }
            }));
        });
    }, 'image/jpeg', 0.7);
}
```

**Default OFF** — same as current page. Video-to-Gemini causes audio stalls.

### Files
| File | Action | Size |
|------|--------|------|
| `static/index_ephemeral_tokens.html` | New (copy + modify) | ~2200 lines |

### Dependencies
- Phase 1 complete (token endpoint available)

---

## Phase 3: Environment Configuration

### 3.1 Local Development

Add `GEMINI_API_KEY` to `.env`:
```
GEMINI_API_KEY=your-gemini-developer-api-key
```

**Important**: This is a **Gemini Developer API** key (from `aistudio.google.com`), NOT a Vertex AI service account. The existing `PROJECT_ID` and Vertex AI auth remain unchanged for vision/pro/imagen/veo3.

### 3.2 Cloud Run Deployment

```bash
gcloud run services update fuse-service \
  --set-env-vars="GEMINI_API_KEY=your-key" \
  --region=us-central1
```

### Files
| File | Action |
|------|--------|
| `.env` | Add `GEMINI_API_KEY` line (local only, gitignored) |

---

## Phase 4: Testing

### 4.1 Test Rubric

#### Unit Tests

| ID | Test | Input | Expected Output | Pass Criteria |
|----|------|-------|-----------------|---------------|
| UT-1 | Token endpoint — success | `GET /api/ephemeral-token` with valid `GEMINI_API_KEY` | `{"status": "ok", "token": "...", "expires_in_seconds": 1800}` | Status 200, token is non-empty string |
| UT-2 | Token endpoint — no API key | `GET /api/ephemeral-token` with `GEMINI_API_KEY=""` | `{"status": "error", "message": "GEMINI_API_KEY not configured on server."}` | Status 200, error message returned |
| UT-3 | Token endpoint — invalid API key | `GET /api/ephemeral-token` with bad key | `{"status": "error", "message": "..."}` | Status 200, error message from Google API |
| UT-4 | Ephemeral page route | `GET /ephemeral` | HTML content with "Ephemeral Tokens" in title | Status 200, contains expected title |
| UT-5 | Ephemeral page — file missing | `GET /ephemeral` without HTML file | `<h1>Ephemeral token page not found</h1>` | Status 404 |
| UT-6 | Audio base64 encoding | PCM16 Int16Array `[0, 32767, -32768]` | Correct base64 string roundtrips | `atob(btoa(data))` matches original |
| UT-7 | Audio base64 decoding | Base64-encoded PCM16 from Gemini | Float32 values in [-1, 1] range | Decoded audio plays correctly |
| UT-8 | Downsampling 48kHz→16kHz | 512 samples at 48kHz | ~170 samples at 16kHz | Length ≈ input * (16000/48000) |

#### Integration Tests

| ID | Test | Steps | Pass Criteria |
|----|------|-------|---------------|
| IT-1 | Full token → connect flow | 1. Start server with `GEMINI_API_KEY` set<br>2. Open `/ephemeral` in browser<br>3. Click "Start Session" | WebSocket connects, setupComplete received, diagnostics begin |
| IT-2 | Audio round-trip | 1. Connect session<br>2. Speak "Hello FUSE" | Gemini responds with audio, played through speakers |
| IT-3 | Input transcription | 1. Connect session<br>2. Speak any sentence | User speech appears in chat panel as "user" message |
| IT-4 | Output transcription | 1. Connect session<br>2. Wait for Gemini greeting | Gemini's speech appears in chat panel as "fuse" message |
| IT-5 | Vision pipeline (HTTP) | 1. Connect session<br>2. Enable camera<br>3. Point at whiteboard | Camera frames sent via HTTP `/vision/frame`, diagram updates |
| IT-6 | System Status panel | 1. Load `/ephemeral`<br>2. Click Status button | Redis: red, Gemini Live (using Ephemeral Tokens): green (if Gemini accessible), others: green |
| IT-7 | Session timeout | 1. Connect session<br>2. Wait 4 minutes | Warning banner appears at 4:00, session ends at 5:00 |
| IT-8 | Diagnostics — all pass | 1. Connect session<br>2. Speak when prompted<br>3. Camera active | Audio Output: PASS, Mic Input: PASS, Camera: PASS |
| IT-9 | Session overlay | 1. Connect and use session<br>2. Click "End Session" | Session ends, overlay appears with download/visualize options |
| IT-10 | Reconnect after session end | 1. End session<br>2. Click "Start Session" again | New token fetched, new Gemini connection established |
| IT-11 | Latency measurement | 1. Connect session<br>2. Have conversation | Client-side latency logged in connection log |
| IT-12 | Text command input | 1. Connect session<br>2. Type text in command input | Text sent as `realtimeInput.text`, Gemini responds |

#### Acceptance Tests (User-Facing)

| ID | Test | Pass Criteria |
|----|------|---------------|
| AT-1 | Demo scenario: System design brainstorm | User can have 5-minute voice conversation with FUSE about designing a microservices architecture. No 1007 errors, no audio drops. |
| AT-2 | Feature parity | All non-audio features work: camera, vision analysis, diagram rendering, validation, Imagen visualization, Veo3 animation |
| AT-3 | Cold start resilience | Page loads during server cold start, splash screen shows progress, session starts after health check passes |
| AT-4 | Error recovery | If token expires, user gets clear error and can start a new session |

### 4.2 Test Commands

```bash
# Unit test: token endpoint
curl -s http://localhost:8080/api/ephemeral-token | python3 -m json.tool

# Unit test: page route
curl -s http://localhost:8080/ephemeral | head -5

# Integration test: full flow
# Open http://localhost:8080/ephemeral in browser with mic/camera permissions
# Follow diagnostic prompts
```

---

## Implementation Checklist

- [ ] **Phase 1**: Add `GET /api/ephemeral-token` and `GET /ephemeral` to `main.py`
- [ ] **Phase 2**: Create `static/index_ephemeral_tokens.html` with direct Gemini WebSocket
- [ ] **Phase 3**: Set `GEMINI_API_KEY` in environment
- [ ] **Phase 4**: Run test rubric (UT-1 through AT-4)

## Risk Mitigations Built Into Design

1. **Token endpoint failure**: Returns clear JSON error, client shows message to user
2. **WebSocket protocol mismatch**: Setup message format validated against Google docs, setupComplete handshake confirms success before proceeding
3. **Audio format mismatch**: Using identical PCM16 format as Vertex AI path (confirmed same in Gemini docs)
4. **No server-side function calling**: Vision/tools still work via HTTP endpoints — only audio changes
5. **Token expiry**: 30-minute token with 5-minute session timer means token never expires during normal use
