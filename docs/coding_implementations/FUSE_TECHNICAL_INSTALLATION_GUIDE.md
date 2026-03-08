# Technical Implementation Guide: Fuse

## 1. System Architecture Overview
Fuse is a real-time multimodal agent extension designed to manage a continuous stream of audio (Speech) and video (Vision) to drive a stateful Mermaid.js architectural model. It is hosted on Google Cloud Platform (GCP) and leverages Vertex AI and Google Cloud Memory Store.

---

## 2. Phase 1: Environment Setup (GCP Native)
*   **Step 1**: Configure Google GenAI Vertex AI clients with `multimodal` capability enabled. Use the `global` location for the GCP endpoint to access the latest model features.
*   **Step 2**: Ensure `MERMAID_CLI` (mmdc) is available in the environment for live diagram rendering.
*   **Step 3**: Initialize **Google Cloud Memory Store (Redis)** to store a "Session-State Buffer" of recent physical object assignments, ensuring low-latency state access.
*   **Step 4**: Project Configuration:
    *   Project Name: `fuse`
    *   Project ID: `fuse-489616`
    *   Location: `global`

---

## 3. Phase 2: Feature Implementation Logic

### 3.1 Real-Time Whiteboard & Sketch Extraction (The Foundation)
*   **Component**: `VisionStateCapture`.
*   **Logic**: Captures vision frames at 2-5 FPS using **gemini-3.1-flash-lite-preview** for low-latency OCR and extraction.
*   **Implementation**: Analyze differences between frames to detect drawing events.
*   **Action**: If a drawing is detected, trigger a specialized agent to update the Mermaid graph.

### 3.2 "Charades" Mode (Gesture-Based Modeling)
*   **Component**: `GeminiLiveStreamHandler`.
*   **Logic**: Interleaves audio transcripts with vision frame metadata using **Gemini 3.1 Flash Live**.
*   **Step-by-Step**:
    1.  Detect "Keyword Triggers" in speech (e.g., "This node is...").
    2.  Check the `vision_frame` for human hand positioning (using Gemini's spatial detection).
    3.  Map the 2D coordinates of the user's hands to a "Node ID" in the current Mermaid graph.
    4.  Update the state delta for the graph layout.

### 3.3 "Imagine" Mode (Object Simulation & Substitution)
*   **Component**: `ProxyObjectRegistry`.
*   **Logic**: Maintain a `Dict[ObjectID, TechnicalRole]` in **Memory Store**.
*   **Step-by-Step**:
    1.  **Calibration**: User says "This [Object Name] is a [Component Name]."
    2.  **Detection**: Gemini identifies the object's visual bounds.
    3.  **Persistence**: Save mapping to Memory Store (Redis).
    4.  **Reaction**: If the user moves a registered object, trigger logic to update the diagram to reflect spatial relationship changes.

---

## 4. Phase 3: Multi-Agent Validation & Proofing
*   **Critical Step**: Pipe the final architectural state into a proof orchestrator using **Gemini 3.1 Pro** for complex technical reasoning.
*   **Validation**: If the session results in a logically impossible design, the specialized verifier agent interrupts via the Live Audio stream.

---

## 5. Phase 4: Output Generation
1.  **Diagram**: Use high-fidelity generation to represent the final architecture.
2.  **Report**: Auto-generate a succinct report summarizing the session's technical decisions.
3.  **Video**: If enabled, output a summary of the object-movements and final design.

---

## 6. Implementation Compliance
- [x] **No Text-Only**: Uses vision/voice as primary input.
- [x] **GCP Native**: Hosted on GCP, using Vertex AI and Memory Store.
- [x] **Latest Models**: Leverages Gemini 3.1 Pro, 3.1 Flash Live, and gemini-3.1-flash-lite-preview.
- [x] **Agentic**: Employs multiple specialized agents.
