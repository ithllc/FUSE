# DevPost Project Details — Ready to Copy-Paste

**Submission**: Fuse (The Collaborative Brainstorming Intelligence)
**Category**: Live Agents
**Hackathon**: Gemini Live Agent Challenge

---

## Project Story

*Copy the content below directly into the DevPost "About the project" markdown editor.*

```markdown
## Inspiration
As a Marvel Comics fan, I was captivated by how Tony Stark interacted with JARVIS — voice, holograms, and physical objects all feeding into real-time system design. After building the first iteration of Research Wiz AI (researchwiz.ai), I realized the missing piece was a natural interface where voice and vision could replace keyboards and mice for brainstorming complex technical architectures.

## What it does
FUSE lets teams brainstorm system architectures using voice and physical objects in real-time, with Gemini Live converting spoken ideas and whiteboard sketches into validated Mermaid diagrams. You can assign everyday objects as proxy components ("this stapler is our GPU cluster"), and the agent maintains a live, evolving architecture that it validates for logical consistency.

## How we built it
We built a FastAPI backend on Google Cloud Run with three Gemini models: gemini-live-2.5-flash-native-audio for real-time voice via the Live API, gemini-3.1-flash-lite-preview for vision/whiteboard capture, and gemini-3.1-pro-preview for architecture validation. The frontend is a single-page web UI communicating over WebSockets, with Redis (Memorystore) for session state persistence.

## Challenges we ran into
The Gemini Live API required response_modalities set to ["AUDIO"] only — adding "TEXT" caused silent failures. We also had to solve WebSocket-to-Live-API bridging for streaming PCM16 audio at 16kHz from the browser to Gemini and playing back 24kHz responses, which required careful buffer management.

## Accomplishments that we're proud of
We achieved a seamless voice-to-diagram pipeline where you can speak an architecture into existence and see it render in real-time. The proxy object system — where physical items become architecture components — feels genuinely novel and makes brainstorming tactile and collaborative.

## What we learned
Building with the Gemini Live API's native audio mode requires a fundamentally different approach than text-based APIs — you're working with raw audio streams, not structured requests. We also learned that multimodal fusion (voice + vision + state) creates emergent capabilities that neither modality provides alone.

## What's next for Fuse (The Collaborative Brainstorming Intelligence)
We plan to integrate Imagen for photorealistic diagram rendering and Veo3 for animated architecture walkthroughs. Longer term, we're building multi-user session support, persistent project workspaces, and integration with our Research Wiz feasibility analysis platform.
```

---

## Built With

*Copy the tags below into the DevPost "Built with" field (comma-separated).*

```
Python, FastAPI, Google Gemini Live API, Google GenAI SDK, Gemini 2.5 Flash Native Audio, Gemini 3.1 Flash Lite Preview, Gemini 3.1 Pro Preview, Google Cloud Run, Google Cloud Memorystore (Redis), Google Artifact Registry, Mermaid.js, WebSockets, Docker, HTML, CSS, JavaScript
```

---

## "Try it out" Links

| Link | URL |
|------|-----|
| Live App | `https://fuse-service-864533297567.us-central1.run.app` |
| GitHub Repo | `https://github.com/ithllc/FUSE` |

---

## Video Demo Link

*To be filled after recording and uploading to YouTube or Vimeo (must be public).*

```
[YouTube/Vimeo URL here]
```

---

## Image Gallery

*Upload these to the DevPost image gallery (JPG/PNG/GIF, 5MB max, 3:2 ratio recommended):*

- [ ] FUSE UI screenshot — active session with diagram visible
- [ ] Architecture diagram — system overview showing 3 Gemini models, Cloud Run, Redis
- [ ] Proxy objects demo — physical objects on desk with FUSE UI showing assignments
- [ ] Validation results — screenshot showing Gemini Pro validation output

---

## Proof of Google Cloud Deployment

*Provide one of the following:*

1. **Option A**: Short screen recording of GCP Console showing Cloud Run service `fuse-service` running in `us-central1`
2. **Option B**: Link to code file demonstrating Google Cloud API usage — e.g., `https://github.com/ithllc/FUSE/blob/main/src/gemini_live_stream.py` (shows GenAI SDK + Live API integration)

---

## Architecture Diagram

*Upload to image gallery. Should show:*
- Browser (WebSocket client)
- FastAPI server on Cloud Run
- Three Gemini models with their roles:
  - `gemini-live-2.5-flash-native-audio` — Voice streaming (Live API, us-central1)
  - `gemini-3.1-flash-lite-preview` — Vision/whiteboard capture (global)
  - `gemini-3.1-pro-preview` — Architecture validation (global)
- Redis Memorystore — session state
- Mermaid CLI — diagram rendering

---

## Optional Bonus Points Checklist

- [ ] **Content publication**: Blog/video covering how FUSE was built with Google AI models and Google Cloud. Must include "created for the purposes of entering the Gemini Live Agent Challenge hackathon." Share with `#GeminiLiveAgentChallenge`
- [ ] **Automated cloud deployment**: Dockerfile + Cloud Build config in the public repo (already exists: `Dockerfile`, `cloudbuild.yaml`)
- [ ] **GDG membership**: Sign up at https://gdg.community.dev/ and provide public profile link

---

## Submission Checklist (All Required)

- [ ] Text description (Project Story above)
- [ ] Public code repository URL (GitHub)
- [ ] Proof of Google Cloud deployment (screen recording or code link)
- [ ] Architecture diagram (image upload)
- [ ] Demo video (<4 min, YouTube/Vimeo, public, English)
- [ ] Category selected: **Live Agents**
