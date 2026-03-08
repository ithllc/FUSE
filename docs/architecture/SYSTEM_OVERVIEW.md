# System Overview: FUSE (Collaborative Brainstorming Intelligence)

## 1. Core Architecture Pattern
FUSE uses a **Client-Server Multimodal Streaming** pattern. It separates physical media capture (client-side) from high-stakes technical reasoning and state management (server-side/GCP).

```mermaid
graph TD
    subgraph Browser Client
        B1[Webcam + Microphone] --> B2[Web UI - index.html]
    end

    subgraph Python Client
        C1[Webcam/Microphone] --> C2[client_streamer.py]
    end

    subgraph Cloud Run (FastAPI)
        B2 -- WebSocket (/live) --> H1[GeminiLiveStreamHandler]
        C2 -- WebSocket (/live) --> H1
        B2 -- HTTP POST (/vision/frame) --> V1[VisionStateCapture]
        C2 -- HTTP POST (/vision/frame) --> V1
        H1 <--> S1[SessionStateManager]
        V1 --> S1
        S1 -- Periodic --> P1[ProofOrchestrator]
        S1 -- GET (/render) --> R1[DiagramRenderer]
    end

    subgraph Google Vertex AI
        H1 <--> G1[Gemini 2.5 Flash Live API]
        V1 <--> G2[Gemini 3.1 Flash Lite Preview]
        P1 <--> G3[Gemini 3.1 Pro Preview]
    end

    subgraph State Store
        S1 <--> R2[(Memory Store Redis)]
    end
```

## 2. Component Roles

| Component | Responsibility | Model / Tool |
| :--- | :--- | :--- |
| **VisionStateCapture** | Real-time OCR and technical sketch extraction. | `gemini-3.1-flash-lite-preview` |
| **GeminiLiveStreamHandler** | Bidirectional multimodal intent (Voice/Gestures). | `gemini-2.5-flash-native-audio-preview-12-2025` |
| **ProofOrchestrator** | High-fidelity architectural reasoning and validation. | `gemini-3.1-pro-preview` |
| **SessionStateManager** | Low-latency state persistence and event logging. | Google Cloud Memory Store (Redis) |
| **DiagramRenderer** | Automated PNG generation for session output. | Mermaid CLI (`mmdc`) |

## 3. Client Options

| Client | Voice Input | Vision Input | Use Case |
| :--- | :--- | :--- | :--- |
| **Web UI** (`index.html`) | Browser microphone (Web Audio API, PCM16 @ 16kHz) | Browser webcam (getUserMedia) | Primary interface for brainstorming sessions |
| **Python Client** (`client_streamer.py`) | PyAudio microphone capture | OpenCV webcam capture | Headless / CLI environments |

## 4. Communication Protocols
*   **WebSockets (`/live`)**: Handles bidirectional binary audio (PCM16) and vision frames between clients and the Gemini Live API session.
*   **REST API (`/vision/frame`)**: Ingests high-resolution JPEG frames for structural diagram analysis via Gemini 3.1 Flash Lite.
*   **REST API (`/state/mermaid`)**: Returns the current Mermaid.js architectural state from Redis.
*   **REST API (`/validate`)**: Triggers on-demand architecture validation via ProofOrchestrator.
