# Multimodal Workflows: FUSE

## 1. Vision Extraction Pipeline (VisionStateCapture) — Two-Pass

This workflow handles the transformation of a physical scene into Mermaid.js code using a two-pass pipeline with scene classification, ROI cropping, and mode-specific extraction.

### Pass 1: Scene Classification
```mermaid
sequenceDiagram
    participant Client as Local Client Streamer
    participant Server as FastAPI (Cloud Run)
    participant Gemini as Gemini 3.1 Flash Lite Preview
    participant Redis as Session State Manager

    Client->>Server: HTTP POST /vision/frame (Binary JPEG)
    Server->>Redis: get_vision_mode()
    alt Mode = "auto"
        alt Cache miss or expired
            Server->>Gemini: Classify Scene (JSON: scene_type, bounding_box, confidence)
            Gemini-->>Server: {"scene_type": "whiteboard", "bounding_box": [...], "confidence": 0.92}
        else Cache hit (≤5 consecutive)
            Server->>Server: Use cached scene classification
        end
    else Explicit mode (whiteboard/imagine/charades)
        Server->>Server: Skip Pass 1, use explicit mode
    end
```

### ROI Cropping
If Pass 1 returns a bounding box with confidence ≥ 0.6, the frame is cropped to the region of interest using OpenCV before Pass 2.

- **Bounding box format**: `[ymin, xmin, ymax, xmax]` normalized 0-1000 (Gemini standard)
- **Descale**: `pixel_coord = int(normalized * image_dim / 1000)`
- **Fallback**: If confidence is below threshold or crop fails, the full frame is used

### Pass 2: Mode-Specific Extraction
```mermaid
sequenceDiagram
    participant Server as FastAPI (Cloud Run)
    participant Redis as Session State Manager
    participant Gemini as Gemini 3.1 Flash Lite Preview

    Server->>Redis: get_architectural_state() + get_proxy_registry() + get_recent_transcript()
    Server->>Server: Build mode-specific prompt with context injection
    Server->>Gemini: Extract Architecture (Cropped Frame + Mode Prompt)
    Gemini-->>Server: Mermaid.js code
    Server->>Server: Merge heuristic (avoid replacing rich diagram with partial view)
    Server->>Redis: update_architectural_state(mermaid_code)
    Server->>Redis: log_event("vision_update", {scene_type, confidence, latency_ms})
    Server-->>Client: 200 OK (Success, Mermaid Length)
```

### Mode-Specific Prompts

| Mode | Trigger | Context Injected | Prompt Focus |
|------|---------|-----------------|--------------|
| **Whiteboard** | scene_type=`whiteboard` or mode=`whiteboard` | Current Mermaid state | Isolate writing surface, extract boxes/arrows/labels |
| **Imagine** | scene_type=`objects` or mode=`imagine` | Proxy registry + Current Mermaid state | Identify assigned objects, map spatial arrangement to architecture |
| **Charades** | scene_type=`gesture` or mode=`charades` | Recent transcript + Current Mermaid state | Interpret hand gestures, cross-reference with voice context |
| **Fallback** | scene_type=`mixed`/`unclear` | Current Mermaid state | Generic architecture extraction |

### Frame Debouncing
The `/vision/frame` endpoint implements frame-level debouncing: if a frame arrives while a previous frame is still being processed, it is dropped with `{"status": "skipped"}`. This prevents processing backlog during continuous streaming.

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

## 3. Vision Mode Switching

Users can switch vision modes via three mechanisms:

| Method | Endpoint / Mechanism | Example |
|--------|---------------------|---------|
| **UI Dropdown** | `POST /vision/mode` | Select "Whiteboard" from dropdown in camera panel |
| **Text Command** | `POST /command` | Type "whiteboard mode" or "switch to imagine mode" |
| **Frame Override** | `POST /vision/frame?mode=whiteboard` | Query parameter on frame submission |

Supported modes: `auto`, `whiteboard`, `imagine`, `charades`

## 4. Transcript Logging for Context Injection

Both user text messages and model text responses are logged as `voice_input` events in Redis during the WebSocket session. These events are retrieved by `get_recent_transcript()` and injected into the Charades mode prompt for gesture-voice cross-referencing.

## 5. On-Demand Rendering Workflow
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

## 6. Photorealistic Visualization Pipeline (Imagen + Veo 3)

This workflow transforms Mermaid diagrams into photorealistic images and animated videos.

```mermaid
sequenceDiagram
    participant User as Web Browser / Client
    participant Server as FastAPI
    participant Redis as Session State Manager
    participant MST as MermaidSceneTranslator
    participant Imagen as Imagen 4.0
    participant Veo3 as Veo 3.0

    User->>Server: GET /render/realistic
    Server->>Redis: get_architectural_state()
    Redis-->>Server: mermaid_code
    Server->>MST: translate(mermaid_code)
    MST-->>Server: Scene description (natural language)
    Server->>Imagen: generate_images(scene_prompt)
    Imagen-->>Server: PNG image bytes
    Server-->>User: Binary Image Response (image/png)

    User->>Server: GET /render/animate
    Server->>Imagen: generate (if not cached)
    Imagen-->>Server: PNG image bytes
    Server->>Veo3: generate_videos(image + animation_prompt)
    Note over Server,Veo3: Async polling every 5s (up to 3 min)
    Veo3-->>Server: MP4 video bytes
    Server-->>User: Binary Video Response (video/mp4)
```

### Scene Translation Pipeline

The `MermaidSceneTranslator` converts Mermaid syntax into visual scene descriptions:

1. **Parse nodes**: Extract node IDs and labels using regex patterns
2. **Parse edges**: Extract connections with edge types (-->, ---, -.->)
3. **Parse subgraphs**: Extract zone groupings
4. **Map to visuals**: Match each node label against a visual metaphor dictionary (70+ mappings)
5. **Build scene**: Compose a natural-language description of the entire infrastructure

### Caching

| Layer | TTL | Key |
|-------|-----|-----|
| Imagen in-memory | 5 min | SHA-256 of Mermaid code |
| Veo 3 in-memory | 10 min | SHA-256 of image bytes |
| Disk persistence | Until cleanup | `output/visualizations/`, `output/animations/` |
