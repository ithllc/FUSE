# System Overview: FUSE (Collaborative Brainstorming Intelligence)

## 1. Core Architecture Pattern
FUSE uses a **Client-Server Multimodal Streaming** pattern. It separates physical media capture (client-side) from high-stakes technical reasoning and state management (server-side/GCP).

```mermaid
graph TD
    subgraph Local Client
        C1[Webcam/Microphone] --> C2[client_streamer.py]
    end

    subgraph Cloud Run (FastAPI)
        C2 -- WebSocket (/live) --> H1[GeminiLiveStreamHandler]
        C2 -- HTTP POST (/vision/frame) --> V1[VisionStateCapture]
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

## 3. Communication Protocols
*   **WebSockets (`/live`)**: Handles the raw binary audio and vision frames for the Gemini Live session.
*   **REST API (`/vision/frame`)**: Ingests high-resolution JPEG frames for structural diagram analysis.
*   **Internal RPC**: Used for coordination between the FastAPI orchestrator and the Vertex AI models.
