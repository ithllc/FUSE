# Product Requirement Document: Fuse (The Collaborative Brainstorming Intelligence)

**Project Name**: Fuse  
**Target Hardware**: Google Gemini 3.1 Live API (Multimodal Live Agent)  
**Parent System**: Standalone (Hosted on GCP)

---

## 1. Executive Summary
Fuse is a real-time, vision-and-voice enabled agent designed for high-stakes technical brainstorming sessions. Unlike standard chatbots, Fuse acts as an active participant that can "see" physical environments and "hear" nuance in group discussions to maintain a persistent, evolving technical architecture. It specializes in converting messy, human-centric interactions (drawings, gestures, and object substitution) into structured, verifiable system designs.

## 2. Core User Personas
*   **The System Architect**: Needs to quickly draft and iterate on complex diagrams without touching a keyboard.
*   **The Research Team**: Needs to brainstorm new hardware/software integrations where physical components may not yet exist.
*   **The Prototypaper**: Needs to use everyday objects to simulate high-tech infrastructure during rapid ideation.

## 3. Key Feature Pillars

### 3.1 Live Whiteboard & Sketch Extraction (The Foundation)
*   **Function**: Real-time monitoring of a physical or digital whiteboard.
*   **Mechanism**: Continuous vision frames are processed to detect entities (nodes) and relationships (edges).
*   **Output**: Live Mermaid.js code generation and rendering.

### 3.2 "Charades" Mode (Gesture-Based Modeling)
*   **Function**: Contextual understanding of technical concepts through physical acting and spatial reference.
*   **Mechanism**: The agent uses Gemini's vision capability to track hand movements and body stance in sync with audio. 
*   **Example**: A user mimes the shape of a "Distributed Database" in the air. The agent hears "It needs to look like a ring" and maps the gesture to a high-availability ring topology in the Mermaid code.
*   **Logic**: Fusion of `vision_frame` analysis and `speech_to_text_intent`.

### 3.3 "Imagine" Mode (Object Simulation & Substitution)
*   **Function**: Using everyday objects (coffee mugs, pens, staplers) as proxies for technical components.
*   **Mechanism**: Users "assign" roles to objects (e.g., "This stapler is our GPU cluster"). The agent maintains a spatial map of these proxies.
*   **Example**: As the user moves the "GPU Stapler" closer to the "Monitor Mug," the agent updates the architecture diagram to reflect a change in network latency or connection type.

### 3.4 Multi-Agent Logic Integration
*   **Validation**: Uses specialized agents to interrupt the session if a brainstormed idea violates physical or logical constraints.
*   **Synthesis**: Automatically generates a Feasibility Report based on the final visual state.

## 4. Technical Constraints & Compliance
*   **No "Text-In/Text-Out"**: Primary interaction is Vision/Voice -> Dynamic Diagram.
*   **No Basic RAG**: Uses real-time physical context, not just static PDF queries.
*   **Latency**: Must achieve < 500ms response time for gesture recognition to feel "Live."
*   **Deployment**: Hosted on Google Cloud Platform (Project: fuse, ID: fuse-489616).
*   **Architecture**: Uses Vertex AI and Google Cloud Memory Store (Redis).

## 5. Success Metrics
*   **Recognition Accuracy**: Correct identification of 90% of technical gestures in "Charades" mode.
*   **Diagram Fidelity**: 1:1 match between physical object placement and Mermaid.js coordinates.
*   **User Engagement**: Reduction in "Time to First Draft" for complex system architectures by 60%.
