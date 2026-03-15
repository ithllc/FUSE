# Test Script: Charades Mode (Gestures)

**Purpose**: End-to-end test of FUSE using hand gestures and body positioning to describe architecture topologies.
**Duration**: ~5 minutes
**What you need**: Your hands and enough space for the camera to see your upper body/hands clearly.

---

## Setup

1. Open https://fuse-service-864533297567.us-central1.run.app in Chrome
2. Wait for the splash page countdown to finish
3. Position your camera so it can see your hands and upper body clearly
4. Good lighting is important — avoid backlighting (don't sit in front of a window)

---

## Phase 1: Pre-Session Diagnostics

1. Click **"Start Session"**
   - _Expected_: Camera and microphone activate, countdown starts

2. When prompted, say: **"Hello FUSE"**
   - _Expected_: All 3 diagnostics pass (Mic, Audio Output, Camera)
   - _Expected_: "Session active" appears in connection log

---

## Phase 2: Switch to Charades Mode

3. Say:
   > **"Switch to charades mode"**
   - _Expected_: FUSE responds: "Switched to charades mode"
   - _Expected_: Vision mode dropdown shows "Charades (Gestures)"

---

## Phase 3: Describe a Star Topology with Gestures

In charades mode, FUSE cross-references what it sees (your gestures) with what it hears (your voice) to determine the architecture topology.

4. Hold both hands up with fingers spread outward from a central point (like a starburst) and say:
   > **"I'm showing you a star topology. There's a central hub in the middle, and five nodes radiate outward from it."**
   - _Expected_: Vision pipeline captures your gesture
   - _Expected_: FUSE responds describing a star/hub-and-spoke topology
   - _Expected_: Diagram panel updates with a Mermaid diagram showing a central hub connected to 5 nodes

5. Ask FUSE to confirm what it sees:
   > **"FUSE, look at my hands. What topology am I showing you?"**
   - _Expected_: Connection log shows "TOOL: capture_and_analyze_frame ✓"
   - _Expected_: FUSE describes the gesture and the topology it interprets

---

## Phase 4: Describe a Pipeline with Gestures

6. Hold your hands flat, one in front of the other, and move them left to right in a line. Say:
   > **"Now I'm showing a pipeline. Data flows from left to right through three stages: ingestion, processing, and storage."**
   - _Expected_: Vision captures the left-to-right hand motion
   - _Expected_: FUSE describes a linear pipeline
   - _Expected_: Diagram updates to show: Ingestion → Processing → Storage

7. Refine with voice:
   > **"Actually, there should be a queue between ingestion and processing, and the storage stage should write to both a data lake and a data warehouse."**
   - _Expected_: FUSE acknowledges the refinement
   - _Expected_: Diagram adds the queue node and the branching storage

---

## Phase 5: Describe a Ring Topology with Gestures

8. Make a circle shape with your hands (or trace a circle in the air) and say:
   > **"This is a ring topology. Four services are connected in a circle: Service A connects to Service B, B to C, C to D, and D back to A."**
   - _Expected_: Vision detects the circular gesture
   - _Expected_: FUSE describes a ring/circular topology
   - _Expected_: Diagram shows 4 nodes in a cycle

9. Ask about the combined architecture:
   > **"What does the full architecture look like now with everything we've discussed?"**
   - _Expected_: Connection log shows "TOOL: get_session_context ✓"
   - _Expected_: FUSE summarizes all topologies that have been captured

---

## Phase 6: Architecture Validation

10. Ask verbally:
    > **"Validate the ring topology. Is there a risk if one of the services goes down?"**
    - _Expected_: FUSE explains that a ring topology has a single point of failure — if any node fails, the ring breaks
    - _Expected_: May suggest adding redundant paths or a mesh overlay

11. Click **"Run Validation"** in the bottom-right panel
    - _Expected_: Written validation report covering all captured topologies

---

## Phase 7: Visualization (Imagen)

12. Click **"Visualize"** in the diagram panel
    - _Expected_: Photorealistic image generates (10-30 seconds)
    - _Expected_: Architecture components rendered as visual metaphors
    - _Expected_: Pipeline stages shown as processing facilities
    - _Expected_: Ring topology shown as interconnected structures

---

## Phase 8: Animation (Veo 3)

13. Click **"Animate"** in the diagram panel
    - _Expected_: Animated walkthrough generates (30-120 seconds)
    - _Expected_: Video shows data flowing through the pipeline and ring structures

---

## Phase 9: End Session

14. Click **"End Session"**
    - _Expected_: "WebSocket closed: Normal closure" (code 1000)
    - _Expected_: Post-session overlay with session summary

---

## Gesture Reference Guide

Use these gestures alongside voice descriptions for best results:

| Gesture | Voice Description | Expected Topology |
|---------|-------------------|-------------------|
| Fingers spread from center | "Star topology with a central hub" | Hub-and-spoke |
| Hands moving left to right | "Pipeline with three stages" | Linear flow |
| Circular hand motion | "Ring with four services" | Circular/ring |
| Hands forming a tree/branches | "Hierarchy with a root node branching out" | Tree/hierarchy |
| Hands forming a mesh/grid | "Mesh network where everything connects" | Full mesh |
| One hand above the other | "Two-tier: frontend above, backend below" | Layered |

**Key**: Charades mode works best when you **speak and gesture simultaneously**. The voice gives FUSE the technical vocabulary, and the gesture gives it spatial context. Neither alone is as effective as both together.

---

## What to Check in the Connection Log

| Entry | Meaning |
|-------|---------|
| `TOOL: capture_and_analyze_frame ✓ (XXXms)` | Gesture captured and analyzed |
| `TOOL: get_session_context ✓ (XXXms)` | Session state retrieved |
| `Audio session reconnected` | Auto-reconnect worked (issue #18) |
| `Session resumption handle updated` | Resumption token captured |

## What to Check in the Chat

- User transcript entries match what you said
- FUSE transcript entries describe the gestures and topologies correctly
- System messages show mode switches and diagnostic results
