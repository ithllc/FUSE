# FUSE Demo Video Storyboard

**Target**: Gemini Live Agent Challenge — DevPost Submission
**Max Duration**: 4 minutes (only first 4 minutes evaluated)
**Upload**: YouTube or Vimeo (public), link provided on DevPost submission form
**Language**: English (or English subtitles)
**Category**: Live Agents

---

## Judging Criteria Alignment

| Criteria | Weight | Where We Hit It |
|----------|--------|-----------------|
| Innovation & Multimodal UX | 40% | Core Demo (1:10–2:20) — voice, vision, proxy objects, interruption handling |
| Technical Implementation | 30% | Architecture & Cloud Proof (2:50–3:20) — 3-model pipeline, Cloud Run, Redis |
| Demo & Presentation | 30% | The Hook (0:00–0:30) — Iron Man inspiration, problem/solution story |

---

## Storyboard

### 0:00–0:30 — The Hook (Inspiration + Problem)

**On screen**: Quick montage or still of Tony Stark/JARVIS holographic interface, then cut to FUSE UI idle state.

**Narration**:
> "Every Marvel fan remembers how Tony Stark built Iron Man — talking to JARVIS, moving holograms with his hands, using physical objects to prototype in real-time. After building Research Wiz AI, I asked: what if technical brainstorming actually worked like that?"

> "Today, architecture brainstorming is fragmented — whiteboards don't validate, diagramming tools don't listen, and ideas die between meetings."

**Key points**:
- Personal, memorable origin story
- Clear problem statement
- Sets up the "why" before the "what"

---

### 0:30–0:50 — The Solution (What FUSE Does)

**On screen**: FUSE UI in idle state, camera showing the workspace.

**Narration**:
> "FUSE is a real-time collaborative brainstorming agent. Speak your architecture, point your camera at a whiteboard, assign physical objects as components — and watch a validated diagram build itself."

**Key points**:
- One-sentence value prop
- Name all three interaction modes (voice, vision, proxy objects)

---

### 0:50–1:10 — Start Session (Live Demo Begins)

**On screen**: Click "Start Session" button. Camera and mic auto-activate. Status changes to "Connected."

**Narration**:
> "When we start a session, FUSE connects to the Gemini Live API. Camera and microphone activate automatically — the agent can now see and hear everything in our workspace."

**Checklist**:
- [ ] Show "Start Session" click
- [ ] Camera feed appears in Live Camera Feed panel
- [ ] Mic icon goes active (red pulse)
- [ ] Status badge: "Disconnected" → "Connected" (green)
- [ ] Button changes to red "End Session"

---

### 1:10–2:20 — Core Multimodal Demo (The Money Shot)

This is the longest and most critical segment. It demonstrates the 40% Innovation & Multimodal UX criteria.

#### Voice Interaction (1:10–1:35)

**On screen**: Speaking naturally while Architecture Diagram panel updates in real-time.

**Narration / Live speech**:
> "Let's design a microservices architecture. We need an API gateway that routes to three services — a user service, an order service, and a payment service."

**Checklist**:
- [ ] Speak naturally (no typing)
- [ ] Mermaid diagram renders/updates in real-time as you speak
- [ ] Show at least 3-4 nodes and connections appearing

#### Proxy Objects — "Imagine" Mode (1:35–1:55)

**On screen**: Pick up physical objects, assign them roles. Move objects around.

**Narration / Live speech**:
> "This coffee cup is our database cluster. This stapler is our GPU array for the ML pipeline. And this pen is the message queue connecting them."

> (Move the stapler closer to the cup) "The GPU cluster needs low-latency access to the database..."

**Checklist**:
- [ ] Hold up each object clearly for camera
- [ ] Speak the assignment ("This X is our Y")
- [ ] Show Proxy Objects tab updating in Session Notes
- [ ] Show diagram updating based on object relationships

#### Whiteboard Capture with Focal Point (1:55–2:10)

**On screen**: Point camera at a hand-drawn whiteboard sketch. Show vision mode selector set to "Auto Detect" or "Whiteboard". Show vision extraction.

**Narration**:
> "I've sketched a rough network topology on the whiteboard. FUSE's two-pass vision system automatically detects the whiteboard, crops to just the drawing surface — ignoring me and the room — and extracts the structure into our diagram."

**Checklist**:
- [ ] Pre-draw a simple architecture sketch on a whiteboard
- [ ] Show the Vision Mode dropdown in the camera panel (set to "Auto Detect")
- [ ] Point camera at it, click "Capture Frame"
- [ ] Show diagram updating with extracted structure
- [ ] Optionally: switch to "Imagine (Objects)" mode to show mode switching in action

#### Interruption Handling (2:10–2:20)

**On screen**: Interrupt mid-sentence, show agent handles it gracefully.

**Narration / Live speech**:
> "Actually wait — let me change that. The payment service should connect directly to—" (pause, rephrase) "—actually, route it through the message queue instead."

**Checklist**:
- [ ] Start a statement, interrupt yourself
- [ ] Show the agent adapts without breaking
- [ ] Diagram reflects the corrected architecture

---

### 2:20–2:50 — Validation (Technical Depth)

**On screen**: Click "Validate Diagram" button. Switch to Validation tab. Show results.

**Narration**:
> "Now let's validate this architecture. FUSE uses Gemini 3.1 Pro to analyze the diagram for logical inconsistencies, bottlenecks, and single points of failure."

> (After results appear) "It caught that our payment service has no redundancy — a single point of failure. Let's fix that..."

**Checklist**:
- [ ] Click "Validate Diagram"
- [ ] Show loading state → results appear
- [ ] Toggle between "Architecture Diagram" and "Validation" tabs
- [ ] Show a real finding (bottleneck, SPOF, missing redundancy)
- [ ] Optionally: speak a fix and show diagram update

---

### 2:50–3:20 — Architecture & Cloud Proof

**On screen**: Architecture diagram overlay or screen share of GCP console / code.

**Narration**:
> "Under the hood, FUSE runs three specialized Gemini models: Live 2.5 Flash for native audio streaming, 3.1 Flash Lite for vision and whiteboard capture, and 3.1 Pro for architecture validation. The backend is FastAPI on Cloud Run, with session state persisted in Memorystore Redis."

**Visual options** (choose one or combine):
1. Show a pre-made architecture diagram as an image overlay
2. Quick screen share of Cloud Run console showing the deployed service
3. Brief code scroll showing the Gemini SDK integration

**Checklist**:
- [ ] Name all three Gemini models and their roles
- [ ] Show Cloud Run deployment proof (console or URL)
- [ ] Mention Redis for session state
- [ ] Keep it brief — 30 seconds max

---

### 3:20–3:45 — End Session + Outputs

**On screen**: Click "End Session". Post-session overlay appears.

**Narration**:
> "When the session ends, FUSE presents your outputs. Download the architecture diagram as a PNG, or generate a photorealistic visualization using Imagen and an animated walkthrough using Veo 3."

**Checklist**:
- [ ] Click "End Session"
- [ ] Show overlay with all three CTAs
- [ ] Click "Download Architecture Diagram" — show download
- [ ] Click "Generate Demo" > "Image (Mockup)" — show Imagen generating a photorealistic scene
- [ ] Click "Generate Demo" > "Video (Animation)" — show Veo 3 animated walkthrough
- [ ] Show the realistic view with image and video playback controls

---

### 3:45–4:00 — Closing

**On screen**: FUSE logo / UI. Team names. GitHub URL. Cloud Run URL.

**Narration**:
> "FUSE — Collaborative Brainstorming Intelligence. Built by Frank Ivey and Jeti Olaf. Team #AlwaysLateToEverything. Links in the description."

**On screen text overlay**:
```
FUSE — Collaborative Brainstorming Intelligence
GitHub: github.com/ithllc/FUSE
Live: fuse-service-864533297567.us-central1.run.app

Frank Ivey & Jeti Olaf
#AlwaysLateToEverything
#GeminiLiveAgentChallenge
```

---

## Pre-Filming Checklist

### Environment Setup
- [ ] Clean, well-lit workspace
- [ ] Whiteboard with pre-drawn architecture sketch (simple, legible)
- [ ] Physical objects ready for proxy assignment (coffee cup, stapler, pen)
- [ ] FUSE deployed and accessible (verify Cloud Run service is up)
- [ ] Test WebSocket connection before filming
- [ ] Browser open to FUSE UI, fullscreen or near-fullscreen

### Technical Checks
- [ ] Microphone working and clear audio
- [ ] Camera working with good framing
- [ ] Screen recording software ready (for GCP console proof segment)
- [ ] Internet connection stable (WebSocket + Live API require low latency)

### Recording Plan
- [ ] Record in one continuous take if possible (shows real-time authenticity)
- [ ] If editing, keep cuts minimal — judges want to see "the actual software working"
- [ ] Record GCP console proof as a separate short clip (can be included in submission separately)

### Post-Recording
- [ ] Upload to YouTube or Vimeo (public)
- [ ] Add English subtitles if narration is unclear
- [ ] Verify video is under 4 minutes
- [ ] Copy URL to DevPost submission form
