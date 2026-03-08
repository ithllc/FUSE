# Multimodal Workflows: FUSE

## 1. Vision Extraction Pipeline (VisionStateCapture)
This workflow handles the transformation of a physical technical sketch into Mermaid.js code.

```mermaid
sequenceDiagram
    participant Client as Local Client Streamer
    participant Server as FastAPI (Cloud Run)
    participant Gemini as Gemini 3.1 Flash Lite Preview
    participant Redis as Session State Manager

    Client->>Server: HTTP POST /vision/frame (Binary JPEG)
    Server->>Gemini: Analyze Frame (Prompt: Extract Mermaid)
    Gemini-->>Server: "graph TD; A-->B"
    Server->>Redis: update_architectural_state(mermaid_code)
    Server->>Redis: log_event("vision_update")
    Server-->>Client: 200 OK (Success, Mermaid Length)
```

## 2. "Imagine" Mode: Proxy Object Registry (Live Stream)
This workflow handles real-time voice-to-state object assignments. Voice input is supported from both the **Web UI** (browser microphone via Web Audio API) and the **Python client** (`client_streamer.py` via PyAudio).

### Browser Voice Flow
```mermaid
sequenceDiagram
    participant Browser as Web UI (index.html)
    participant Mic as Browser Microphone
    participant Server as WebSocket /live
    participant GeminiLive as Gemini 2.5 Flash Live API
    participant Speaker as Browser Speakers

    Browser->>Mic: getUserMedia({audio})
    Mic->>Browser: PCM16 @ 16kHz (ScriptProcessorNode)
    Browser->>Server: Binary Audio Frames (Int16Array)
    Server->>GeminiLive: Forward Audio Bytes
    GeminiLive-->>Server: Text Response + Audio Response
    Server-->>Browser: Text (JSON) + Audio (PCM16 Binary)
    Browser->>Speaker: AudioContext playback (24kHz)
```

### Python Client Voice Flow
```mermaid
sequenceDiagram
    participant Client as client_streamer.py
    participant Server as WebSocket /live
    participant GeminiLive as Gemini 2.5 Flash Live API
    participant Redis as Session State Manager

    Client->>Server: Binary Audio ("This stapler is a GPU")
    Server->>GeminiLive: Forward Audio Bytes
    GeminiLive-->>Server: Text Intent ("Acknowledge proxy assignment")
    GeminiLive-->>Client: Audio Response ("Understood, Stapler is now a GPU")
    Server->>Redis: set_object_proxy("stapler", "GPU cluster")
    Server->>Redis: log_event("proxy_assignment")
```

## 3. On-Demand Rendering Workflow
This workflow converts the persisted state into a high-fidelity visual output.

```mermaid
sequenceDiagram
    participant User as Web Browser / Client
    participant Server as FastAPI /render
    participant Redis as Session State Manager
    participant MCLI as Mermaid CLI (mmdc)

    User->>Server: HTTP GET /render
    Server->>Redis: get_architectural_state()
    Redis-->>Server: mermaid_code
    Server->>MCLI: Generate PNG (Forest Theme)
    MCLI-->>Server: latest_architecture.png
    Server-->>User: Binary Image Response (image/png)
```
