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
We built a FastAPI backend on Google Cloud Run with five Gemini models: gemini-2.5-flash-native-audio for real-time voice via the Live API (using ephemeral tokens for direct browser-to-Gemini WebSocket), gemini-3.1-flash-lite-preview for two-pass vision capture (scene classification + mode-specific extraction), gemini-3.1-pro-preview for architecture validation, Imagen 4.0 for photorealistic diagram visualization, and Veo 3.0 for animated architecture walkthroughs. The frontend connects directly to Gemini for audio/video streaming via ephemeral tokens, while using the FastAPI server for vision processing, diagram rendering, validation, and visualization. Session state persists in Redis (Memorystore), and the API key is secured via GCP Secret Manager — never stored in code.

## Challenges we ran into
Our biggest challenge was achieving stable real-time audio with the Gemini Live API. We initially built a server-to-server architecture where the FastAPI backend proxied all audio between the browser and Vertex AI's Live API. This double-hop relay introduced persistent WebSocket 1007 ("invalid audio format") and 1008 ("policy violation") errors caused by timing mismatches when audio frames arrived during session transitions, race conditions during pending tool calls, and an UnboundLocalError that crashed sessions after exactly 5 responses.

After 31 issues and extensive debugging — including A/B testing audio-only vs audio+video, latency instrumentation, session resumption with transparent handles, server-side VAD tuning, and context window compression — we pivoted to **ephemeral tokens** for direct browser-to-Gemini WebSocket communication. This eliminated the server-side audio proxy entirely. But the ephemeral token path brought its own challenges: Gemini sends all WebSocket messages (including JSON) as binary frames (not text), the `BidiGenerateContentConstrained` endpoint requires `?access_token=` (not `?key=`), and the `proactiveAudio` feature doesn't reliably trigger the model to speak first (we solved this with a delayed `realtimeInput.text` trigger).

We also learned that `response_modalities` must be `["AUDIO"]` only — adding `"TEXT"` causes silent failures — and that the browser's `getUserMedia` API requires HTTPS or localhost, which silently blocks mic/camera access on plain HTTP.

## Accomplishments that we're proud of
We achieved a seamless voice-to-diagram pipeline where you can speak an architecture into existence and see it render in real-time. The proxy object system — where physical items become architecture components — feels genuinely novel and makes brainstorming tactile and collaborative.

## What we learned
Building with the Gemini Live API's native audio mode requires a fundamentally different approach than text-based APIs — you're working with real-time audio streams, video frames, and function calls, not structured request/response cycles. We learned that server-to-server audio proxying introduces fragile timing dependencies that direct client connections eliminate. We discovered that ephemeral tokens provide a secure, reliable bridge between server-side API key management and client-side real-time streaming. And we learned that multimodal fusion (voice + vision + state) creates emergent capabilities that neither modality provides alone — when the model can see, hear, and call functions simultaneously, it becomes a genuinely useful brainstorming partner.

## What's next for Fuse (The Collaborative Brainstorming Intelligence)
We plan to introduce FUSE as commercial product for both B2B and B2C domains.
```

---

## Built With

*Copy the tags below into the DevPost "Built with" field (comma-separated).*

```
Python, FastAPI, Google Gemini Live API, Google GenAI SDK, Gemini 2.5 Flash Native Audio, Gemini 3.1 Flash Lite Preview, Gemini 3.1 Pro Preview, Imagen 4.0, Veo 3.0, Google Cloud Run, Google Cloud Memorystore (Redis), Google Cloud Secret Manager, Google Artifact Registry, Ephemeral Tokens, Mermaid.js, WebSockets, Docker, HTML, CSS, JavaScript
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
- Browser → Gemini Live API (direct WebSocket via ephemeral tokens — audio + video + function calling)
- Browser → FastAPI server on Cloud Run (HTTP — vision, diagrams, validation, visualization)
- FastAPI → Gemini API (ephemeral token generation via Secret Manager)
- Five Gemini models with their roles:
  - `gemini-2.5-flash-native-audio` — Voice + video streaming (Live API, direct to browser)
  - `gemini-3.1-flash-lite-preview` — Vision/whiteboard capture (server-side, global)
  - `gemini-3.1-pro-preview` — Architecture validation (server-side, global)
  - `imagen-4.0-generate-001` — Photorealistic diagram visualization (server-side, us-central1)
  - `veo-3.0-generate-preview` — Animated architecture walkthroughs (server-side, us-central1)
- Redis Memorystore — session state
- GCP Secret Manager — GEMINI_API_KEY storage
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
