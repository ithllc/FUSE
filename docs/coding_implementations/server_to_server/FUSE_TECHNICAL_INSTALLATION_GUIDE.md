# Technical Implementation Guide: Fuse

## 1. System Architecture Overview
Fuse is a real-time multimodal agent extension designed to manage a continuous stream of audio (Speech) and video (Vision) to drive a stateful Mermaid.js architectural model. It follows a **Client-Server Multimodal Streaming** pattern to bridge physical environments with cloud-based reasoning.

---

## 2. Phase 1: Environment Setup (GCP Native)
*   **Step 1**: Configure Google GenAI Vertex AI clients with `multimodal` capability enabled.
*   **Step 2**: **Diagram Rendering Engine**: The environment includes Node.js and `@mermaid-js/mermaid-cli` (mmdc) for high-fidelity PNG generation.
*   **Step 3**: **State Management**: Uses **Google Cloud Memory Store (Redis)** to persist session state, architectural deltas, and proxy object registries.
*   **Step 4**: **Network Connectivity**:
    *   **WebSocket (`/live`)**: Bidirectional binary stream for Gemini 2.5 Flash Live API (Audio/Vision/Text).
    *   **HTTP POST (`/vision/frame`)**: Ingests individual JPEG frames for low-latency OCR via Gemini 3.1 Flash Lite.
    *   **HTTP GET (`/render`)**: Triggers the Mermaid CLI to output the latest diagram.

---

## 3. Phase 2: Feature Implementation Logic

### 3.1 Cloud-Native Vision Extraction
*   **Component**: `VisionStateCapture`.
*   **Logic**: Instead of local camera access, the server exposes an endpoint to receive compressed JPEG frames from any client.
*   **Process**: Frames are analyzed by **gemini-3.1-flash-lite-preview** for OCR and Mermaid code generation.
*   **Persistence**: Results are pushed to Redis and tracked as `vision_update` events.

### 3.2 "Charades" & "Imagine" Mode (Multimodal Live)
*   **Component**: `GeminiLiveStreamHandler`.
*   **Logic**: Direct pipe between the client WebSocket and the **Gemini 2.5 Flash Live API** session.
*   **Voice Commands**: Real-time intent detection (e.g., "This stapler is a GPU") registers proxy objects in the `SessionStateManager`.
*   **Feedback Loop**: Gemini's audio responses are streamed back to the client via the same WebSocket.

### 3.3 Client-Side Streamer (`client_streamer.py`)
*   **Role**: Bridges physical hardware (Webcam, Mic) to the Cloud Run service.
*   **Dependencies**: `opencv-python`, `websockets`, `pyaudio`.
*   **Function**: Captures local media, compresses it, and establishes the real-time link to the `/live` and `/vision/frame` endpoints.

---

## 4. Phase 3: Multi-Agent Validation & Proofing
*   **Critical Step**: The `ProofOrchestrator` periodically fetches the latest Mermaid code from Redis.
*   **Reasoning**: Uses **Gemini 3.1 Pro Preview** to identify single points of failure, bottlenecks, or logical errors.
*   **Report**: Validation reports are stored in Redis and can be retrieved by the orchestrator for session feedback.

---

## 5. Phase 4: Output Generation
1.  **Diagram**: On-demand PNG rendering via the `/render` endpoint.
2.  **State**: Full session history and proxy registry available in Memory Store.

---

## 6. Implementation Compliance
- [x] **No Text-Only**: Uses vision/voice as primary input.
- [x] **GCP Native**: Hosted on GCP, using Vertex AI, Cloud Build, and Memory Store.
- [x] **Latest Models**: Leverages Gemini 3.1 Pro Preview, 2.5 Flash Live API, and gemini-3.1-flash-lite-preview.
- [x] **Client-Server Sync**: Uses WebSockets for low-latency multimodal interaction.
