# Ephemeral Token Architecture — Mermaid Diagrams

**Issue**: #38
**Generated from**: `ARCHITECTURE.md`

---

## Full System Architecture

```mermaid
graph TD
    subgraph Browser["Browser (Client)"]
        UI["FUSE Web UI<br/>index_ephemeral_tokens.html"]
        MicPipeline["Mic → PCM16 → base64 → JSON"]
        SpkrPipeline["JSON → base64 → PCM16 → Speakers"]
        ToolHandler["Function Call Handler<br/>capture_and_analyze_frame<br/>get_session_context<br/>set_proxy_object"]
        TranscriptDisplay["Session Notes<br/>Transcript + Proxy Objects"]
        DiagramPanel["Architecture Diagram<br/>Mermaid.js Renderer"]
    end

    subgraph GCP["GCP (FastAPI on Cloud Run)"]
        FastAPI["FastAPI Server"]
        TokenEndpoint["/api/ephemeral-token"]
        VisionPipeline["VisionStateCapture<br/>gemini-3.1-flash-lite-preview"]
        ProofOrch["ProofOrchestrator<br/>gemini-3.1-pro-preview"]
        DiagramRenderer["Diagram Renderer<br/>Mermaid CLI"]
        ImagenViz["Imagen 4.0<br/>Photorealistic Viz"]
        Veo3Anim["Veo 3.0<br/>Animated Walkthrough"]
        Redis["Redis Memorystore<br/>Session State"]
        SecretMgr["Secret Manager<br/>GEMINI_API_KEY"]
    end

    subgraph GeminiAPI["Gemini Live API (Google Cloud)"]
        GeminiLive["gemini-live-2.5-flash<br/>-native-audio"]
        EphemeralAuth["Ephemeral Token Auth<br/>Single-use, 30min TTL"]
    end

    %% Token Flow
    UI -->|"1. GET /api/ephemeral-token"| TokenEndpoint
    SecretMgr -->|"API Key"| TokenEndpoint
    TokenEndpoint -->|"auth_tokens.create()"| EphemeralAuth
    EphemeralAuth -->|"ephemeral token"| TokenEndpoint
    TokenEndpoint -->|"{ token }"| UI

    %% Direct Audio WebSocket
    MicPipeline -->|"WSS + access_token<br/>realtimeInput JSON"| GeminiLive
    GeminiLive -->|"serverContent JSON<br/>base64 audio"| SpkrPipeline
    GeminiLive -->|"inputTranscription<br/>outputTranscription"| TranscriptDisplay
    GeminiLive -->|"toolCall"| ToolHandler

    %% Function Calls from Browser
    ToolHandler -->|"toolResponse"| GeminiLive
    ToolHandler -->|"POST /vision/frame"| VisionPipeline
    ToolHandler -->|"GET /state/mermaid"| Redis

    %% HTTP REST Features (Browser → Server)
    UI -->|"GET /health"| FastAPI
    UI -->|"GET /validate"| ProofOrch
    UI -->|"GET /render"| DiagramRenderer
    UI -->|"GET /render/realistic"| ImagenViz
    UI -->|"GET /render/animate"| Veo3Anim
    UI -->|"POST /vision/frame"| VisionPipeline

    %% Server Internal
    VisionPipeline --> Redis
    FastAPI --> Redis

    %% Diagram Display
    DiagramRenderer --> DiagramPanel
    ImagenViz --> DiagramPanel
    Veo3Anim --> DiagramPanel
```

---

## Session Lifecycle Flow

```mermaid
sequenceDiagram
    participant B as Browser
    participant S as FastAPI Server
    participant SM as Secret Manager
    participant G as Gemini Live API

    Note over B: Page Load
    B->>S: GET / (serve UI)
    S-->>B: index_ephemeral_tokens.html
    B->>S: GET /health
    S-->>B: Component status JSON

    Note over B: Session Start
    B->>S: GET /api/ephemeral-token
    S->>SM: Read GEMINI_API_KEY
    SM-->>S: API Key
    S->>G: auth_tokens.create(uses=1, expire=30min)
    G-->>S: { token: "ephemeral_..." }
    S-->>B: { status: ok, token }

    Note over B: WebSocket Connection
    B->>G: WSS connect + ?access_token=...
    B->>G: JSON setup (model, config, tools, system_instruction)
    G-->>B: setupComplete

    Note over B,G: Bidirectional Audio Streaming
    loop Audio Loop
        B->>G: { realtimeInput: { audio: { data: base64 } } }
        G-->>B: { serverContent: { modelTurn: { parts: [inlineData] } } }
    end

    Note over B,G: Transcriptions
    G-->>B: { serverContent: { inputTranscription: { text } } }
    G-->>B: { serverContent: { outputTranscription: { text } } }

    Note over B,G: Function Calling
    G-->>B: { toolCall: { functionCalls: [...] } }
    B->>S: POST /vision/frame (if capture requested)
    S-->>B: { mermaid_code, scene_type }
    B->>G: { toolResponse: { functionResponses: [...] } }
    B->>S: POST /api/tool-event (fire-and-forget logging)

    Note over B: Session End (timeout or user)
    B->>G: WebSocket close
    B->>S: POST /api/session-event (disconnect metrics)
```

---

## Client-Side Action Flow

```mermaid
graph LR
    subgraph UserActions["User Actions"]
        StartSession["Click Start Session"]
        Speak["Speak to Mic"]
        CaptureFrame["Capture Frame"]
        EndSession["Click End Session<br/>or 5min Timeout"]
    end

    subgraph ClientProcessing["Browser Processing"]
        FetchToken["Fetch Ephemeral Token<br/>GET /api/ephemeral-token"]
        OpenWS["Open WSS to Gemini<br/>with access_token"]
        SendSetup["Send setup JSON<br/>model + config + tools"]
        EncodePCM["PCM16 → base64 → JSON"]
        DecodeAudio["base64 → PCM16 → Play"]
        HandleTranscript["Buffer Partials → Full Sentences"]
        HandleToolCall["Execute Tool Call<br/>via HTTP to Server"]
        SendToolResponse["Send toolResponse<br/>back to Gemini WSS"]
        RenderMermaid["Extract + Render Mermaid"]
        ShowOverlay["Show Session Complete<br/>Overlay"]
    end

    StartSession --> FetchToken --> OpenWS --> SendSetup
    Speak --> EncodePCM -->|"WSS"| OpenWS
    OpenWS -->|"audio response"| DecodeAudio
    OpenWS -->|"transcription"| HandleTranscript
    OpenWS -->|"toolCall"| HandleToolCall --> SendToolResponse
    HandleTranscript --> RenderMermaid
    CaptureFrame -->|"POST /vision/frame"| HandleToolCall
    EndSession --> ShowOverlay
```

---

## GCP Action Flow

```mermaid
graph TD
    subgraph CloudRun["Cloud Run — FastAPI"]
        PageRoute["GET / → Serve UI"]
        HealthRoute["GET /health → Ping All Components"]
        TokenRoute["GET /api/ephemeral-token"]
        VisionRoute["POST /vision/frame"]
        ValidateRoute["GET /validate"]
        RenderRoute["GET /render"]
        RealisticRoute["GET /render/realistic"]
        AnimateRoute["GET /render/animate"]
        EventRoutes["POST /api/session-event<br/>POST /api/tool-event"]
    end

    subgraph GeminiModels["Gemini AI Models"]
        FlashLite["gemini-3.1-flash-lite-preview<br/>Vision + Scene Classification"]
        Pro["gemini-3.1-pro-preview<br/>Architecture Validation"]
        LiveAudio["gemini-live-2.5-flash-native-audio<br/>Conversational AI"]
    end

    subgraph MediaModels["Media Generation"]
        Imagen["imagen-4.0-generate-001<br/>Photorealistic Images"]
        Veo3["veo-3.0-generate-preview<br/>Animated Video"]
    end

    subgraph Storage["Persistence"]
        RedisStore["Redis Memorystore<br/>10.8.239.3:6379<br/>Session State + Events"]
        SecretMgr2["Secret Manager<br/>GEMINI_API_KEY"]
        CloudLogging["Cloud Logging<br/>Structured Events"]
    end

    TokenRoute -->|"API Key"| SecretMgr2
    TokenRoute -->|"auth_tokens.create()"| LiveAudio
    VisionRoute --> FlashLite
    VisionRoute --> RedisStore
    ValidateRoute --> Pro
    RealisticRoute --> Imagen
    AnimateRoute --> Veo3
    HealthRoute --> RedisStore
    HealthRoute --> FlashLite
    HealthRoute --> Pro
    HealthRoute --> Imagen
    HealthRoute --> Veo3
    EventRoutes --> CloudLogging
```
