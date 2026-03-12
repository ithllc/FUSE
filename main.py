import asyncio
import base64
import logging
import os
import json
import sys
import time
import traceback
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

# Configure logging to stderr so Cloud Run captures it
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fuse")

from src.vision.vision_state_capture import VisionStateCapture
from src.audio.gemini_live_stream_handler import GeminiLiveStreamHandler
from src.state.session_state_manager import SessionStateManager
from src.agents.proof_orchestrator import ProofOrchestrator
from src.output.diagram_renderer import DiagramRenderer
from src.output.imagen_diagram_visualizer import ImagenDiagramVisualizer
from src.output.veo3_diagram_animator import Veo3DiagramAnimator
from google.genai import types as genai_types

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID", "fuse-489616")
LOCATION = os.getenv("LOCATION", "global")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

# Global handlers for API access
live_handler = None
diagram_renderer = None
state_manager = None
vision_capture = None
proof_orchestrator = None
imagen_visualizer = None
veo3_animator = None

# Frame processing debounce (Phase 4)
_processing_frame = False

# Initialize FastAPI app
app = FastAPI(title="FUSE: Collaborative Brainstorming Intelligence API")

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serves the FUSE web interface."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/health")
async def health_check():
    """Deep health check — verifies all downstream components."""
    components = {}

    # 1. Redis
    try:
        if state_manager:
            t0 = time.time()
            state_manager.r.ping()
            latency_ms = int((time.time() - t0) * 1000)
            components["redis"] = {"status": "ok", "latency_ms": latency_ms}
        else:
            components["redis"] = {"status": "error", "detail": "State manager not initialized"}
    except Exception as e:
        components["redis"] = {"status": "error", "detail": str(e)}

    # 2. Component initialization checks
    component_checks = {
        "gemini_live": live_handler,
        "gemini_vision": vision_capture,
        "gemini_pro": proof_orchestrator,
        "diagram_renderer": diagram_renderer,
        "imagen": imagen_visualizer,
        "veo3": veo3_animator,
    }
    for name, handler in component_checks.items():
        if handler is not None:
            components[name] = {"status": "ok"}
        else:
            components[name] = {"status": "error", "detail": "Not initialized"}

    # 3. Session state summary
    session = {}
    if state_manager and components["redis"]["status"] == "ok":
        try:
            diag = state_manager.get_session_diagnostics()
            session["vision_mode"] = diag["vision_mode"]
            session["proxy_count"] = diag["proxy_count"]
            session["diagram_length"] = diag["diagram_length"]
            session["recent_events"] = diag["total_events"]
            session["recent_errors"] = diag["recent_errors"]
        except Exception:
            pass

    all_ok = all(c.get("status") == "ok" for c in components.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "system": "FUSE",
        "project_id": PROJECT_ID,
        "components": components,
        "session": session,
    }

@app.post("/command")
async def trigger_command(text: str):
    """Triggers a simulated voice command."""
    if not live_handler:
        return {"status": "error", "message": "Handler not initialized."}

    response = await live_handler.process_simulated_command(text)
    return {"status": "success", "response": response}

@app.post("/vision/frame")
async def receive_frame(request: Request, mode: Optional[str] = None):
    """Receives a binary image frame. Optional ?mode=whiteboard|imagine|charades override."""
    global _processing_frame

    if not vision_capture:
        return {"status": "error", "message": "Vision capture not initialized."}

    # Frame debounce: skip if previous frame still processing
    if _processing_frame:
        return {"status": "skipped", "reason": "Previous frame still processing"}

    frame_bytes = await request.body()
    if not frame_bytes:
        return {"status": "error", "message": "No frame data received."}

    # Apply mode override if provided
    if mode and mode in ("whiteboard", "imagine", "charades") and state_manager:
        state_manager.set_vision_mode(mode)

    _processing_frame = True
    try:
        mermaid_code = vision_capture.process_received_frame(frame_bytes)
        return {"status": "success", "mermaid_length": len(mermaid_code)}
    finally:
        _processing_frame = False

@app.get("/vision/mode")
async def get_vision_mode():
    """Returns the current vision processing mode."""
    if not state_manager:
        return {"status": "error", "message": "State manager not initialized."}
    return {"status": "ok", "mode": state_manager.get_vision_mode()}

@app.post("/vision/mode")
async def set_vision_mode(request: Request):
    """Sets the vision processing mode: auto|whiteboard|imagine|charades."""
    if not state_manager:
        return {"status": "error", "message": "State manager not initialized."}
    body = await request.json()
    mode = body.get("mode", "auto")
    if mode not in ("auto", "whiteboard", "imagine", "charades"):
        return {"status": "error", "message": f"Invalid mode: {mode}"}
    state_manager.set_vision_mode(mode)
    return {"status": "ok", "mode": mode}

@app.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles bidirectional multimodal streaming (Audio/Vision/Text).
    Connects the client directly to the Gemini Live session.
    Sends structured status/error messages for client-side diagnostics.
    """
    if not live_handler:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "type": "error",
            "stage": "initialization",
            "message": "Live handler not initialized. Server may still be starting up.",
            "error_type": "InitializationError",
            "detail": "GeminiLiveStreamHandler failed to initialize during server startup."
        }))
        await websocket.close(code=1011)
        return

    await websocket.accept()
    logger.info("WebSocket connection established.")
    logger.info(f"Live handler model: {live_handler.model_id}, location: {live_handler.location}")

    try:
        # Stage: connecting to Gemini
        await websocket.send_text(json.dumps({
            "type": "status",
            "stage": "connecting",
            "message": "Connecting to Gemini Live API..."
        }))

        async with live_handler.client.aio.live.connect(
            model=live_handler.model_id,
            config=live_handler.get_config()
        ) as session:
            # Stage: connected
            logger.info("Gemini Live session connected successfully.")
            await websocket.send_text(json.dumps({
                "type": "status",
                "stage": "connected",
                "message": "Live session active. Running diagnostics...",
                "model": live_handler.model_id,
                "location": live_handler.location
            }))

            # Stage: diagnostics — Gemini's system instruction tells it to greet
            # immediately. No text prompt needed (issues #11, #12).
            await websocket.send_text(json.dumps({
                "type": "status",
                "stage": "diagnostics",
                "message": "Running pre-session diagnostics..."
            }))

            # Shared flag so tasks can signal each other to stop
            session_active = True

            async def receive_from_client():
                nonlocal session_active
                try:
                    while session_active:
                        message = await websocket.receive()
                        if "bytes" in message:
                            # Wrap PCM16 audio in Blob for Gemini Live SDK
                            audio_blob = genai_types.Blob(
                                data=message["bytes"],
                                mime_type="audio/pcm;rate=16000"
                            )
                            await session.send_realtime_input(audio=audio_blob)
                        elif "text" in message:
                            raw = message["text"]
                            try:
                                parsed = json.loads(raw)
                                text_val = parsed.get("text", raw) if isinstance(parsed, dict) else raw
                            except (json.JSONDecodeError, TypeError):
                                text_val = raw
                            if state_manager:
                                state_manager.log_event("voice_input", {"text": text_val})
                            await session.send(input=text_val, end_of_turn=True)
                except WebSocketDisconnect:
                    logger.info("Client disconnected from WebSocket.")
                except Exception as e:
                    if session_active:
                        logger.error(f"Error in receive_from_client: {e}")
                finally:
                    session_active = False

            async def send_to_client():
                nonlocal session_active
                try:
                    async for response in session.receive():
                        if response is None:
                            break
                        if hasattr(response, 'server_content') and response.server_content:
                            sc = response.server_content
                            if hasattr(sc, 'model_turn') and sc.model_turn and sc.model_turn.parts:
                                for part in sc.model_turn.parts:
                                    if hasattr(part, 'text') and part.text:
                                        await websocket.send_text(json.dumps({"text": part.text}))
                                        if state_manager:
                                            state_manager.log_event("voice_input", {"text": part.text})
                                    if hasattr(part, 'inline_data') and part.inline_data:
                                        await websocket.send_bytes(part.inline_data.data)
                        if hasattr(response, 'text') and response.text:
                            await websocket.send_text(json.dumps({"text": response.text}))
                        if hasattr(response, 'data') and response.data:
                            await websocket.send_bytes(response.data)
                except Exception as e:
                    error_str = str(e)
                    # Gemini session closing with code 1000 is a normal end, not an error
                    if "1000" in error_str:
                        logger.info("Gemini Live session ended normally.")
                    else:
                        logger.error(f"Error in send_to_client: {e}\n{traceback.format_exc()}")
                finally:
                    session_active = False

            # Run both tasks; when either finishes, cancel the other
            tasks = [
                asyncio.create_task(receive_from_client()),
                asyncio.create_task(send_to_client()),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(f"Live session error at stage 'gemini_connect': {error_msg}\n{traceback.format_exc()}")

        # Log as session event for diagnostics
        if state_manager:
            state_manager.log_event("connection_error", {
                "stage": "gemini_connect",
                "error_type": type(e).__name__,
                "detail": str(e),
            })

        # Send structured error to client before closing
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "stage": "gemini_connect",
                "message": f"Live session failed: {error_msg}",
                "error_type": type(e).__name__,
                "detail": str(e)
            }))
        except Exception:
            pass
    finally:
        logger.info("WebSocket connection closed.")

@app.get("/render")
async def render_diagram():
    """Renders the current architectural state into a PNG file."""
    if not state_manager or not diagram_renderer:
        return {"status": "error", "message": "System components not initialized."}

    mermaid_code = state_manager.get_architectural_state()
    if not mermaid_code:
        return {"status": "error", "message": "No architectural state to render."}

    output_path = diagram_renderer.render(mermaid_code)
    if output_path and os.path.exists(output_path):
        return FileResponse(output_path, media_type="image/png")

    return {"status": "error", "message": "Failed to render diagram."}

@app.get("/render/realistic")
async def render_realistic():
    """Generate a photorealistic image of the current architecture using Imagen."""
    if not state_manager or not imagen_visualizer:
        return {"status": "error", "message": "System components not initialized."}

    mermaid_code = state_manager.get_architectural_state()
    if not mermaid_code:
        return {"status": "error", "message": "No architectural state to visualize."}

    image_bytes = await imagen_visualizer.generate(mermaid_code)
    if image_bytes:
        return Response(content=image_bytes, media_type="image/png")

    return {"status": "error", "message": "Failed to generate realistic visualization."}

@app.get("/render/animate")
async def render_animate():
    """Generate an animated walkthrough video from the realistic image using Veo 3."""
    if not state_manager or not imagen_visualizer or not veo3_animator:
        return {"status": "error", "message": "System components not initialized."}

    mermaid_code = state_manager.get_architectural_state()
    if not mermaid_code:
        return {"status": "error", "message": "No architectural state to animate."}

    # Ensure a realistic image exists (generate if needed)
    image_bytes = await imagen_visualizer.generate(mermaid_code)
    if not image_bytes:
        return {"status": "error", "message": "Failed to generate base image for animation."}

    video_bytes = await veo3_animator.animate(
        image_bytes=image_bytes,
        mermaid_code=mermaid_code,
        duration_seconds=6,
    )
    if video_bytes:
        return Response(content=video_bytes, media_type="video/mp4")

    return {"status": "error", "message": "Failed to generate animation."}

@app.get("/render/visualize")
async def render_visualize():
    """Full pipeline: Mermaid -> photorealistic image -> animated video.
    Returns JSON with base64-encoded image and video."""
    if not state_manager or not imagen_visualizer or not veo3_animator:
        return {"status": "error", "message": "System components not initialized."}

    mermaid_code = state_manager.get_architectural_state()
    if not mermaid_code:
        return {"status": "error", "message": "No architectural state to visualize."}

    result = {"status": "success", "image": None, "video": None}

    image_bytes = await imagen_visualizer.generate(mermaid_code)
    if image_bytes:
        result["image"] = base64.b64encode(image_bytes).decode("utf-8")
        result["image_mime"] = "image/png"
    else:
        return {"status": "error", "message": "Image generation failed."}

    video_bytes = await veo3_animator.animate(
        image_bytes=image_bytes,
        mermaid_code=mermaid_code,
        duration_seconds=6,
    )
    if video_bytes:
        result["video"] = base64.b64encode(video_bytes).decode("utf-8")
        result["video_mime"] = "video/mp4"
    else:
        result["video_error"] = "Animation generation failed; image is still available."

    return result

@app.get("/state/mermaid")
async def get_mermaid_state():
    """Returns the current Mermaid.js architectural state from Redis."""
    if not state_manager:
        return {"status": "error", "message": "State manager not initialized."}

    mermaid_code = state_manager.get_architectural_state()
    if not mermaid_code:
        return {"status": "ok", "mermaid_code": None}

    return {"status": "ok", "mermaid_code": mermaid_code}

@app.get("/validate")
async def validate_architecture():
    """Triggers on-demand architecture validation via ProofOrchestrator."""
    if not proof_orchestrator or not state_manager:
        return {"status": "error", "message": "System components not initialized."}

    mermaid_code = state_manager.get_architectural_state()
    if not mermaid_code:
        return {"status": "error", "message": "No architectural state to validate."}

    events = state_manager.get_events(limit=20)
    result = proof_orchestrator.validate_architecture(mermaid_code, events)
    return {"status": "success", **result}


async def run_periodic_validation(interval_seconds: int = 60):
    """Periodically validates the architectural state using ProofOrchestrator."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            if state_manager and proof_orchestrator:
                mermaid_code = state_manager.get_architectural_state()
                if mermaid_code:
                    events = state_manager.get_events(limit=20)
                    result = proof_orchestrator.validate_architecture(mermaid_code, events)
                    state_manager.log_event("validation", {
                        "is_valid": result["is_valid"],
                        "report_length": len(result.get("validation_report", ""))
                    })
                    print(f"Periodic validation: valid={result['is_valid']}")
        except Exception as e:
            print(f"Periodic validation error: {e}")


async def start_agents():
    global live_handler, diagram_renderer, state_manager, vision_capture, proof_orchestrator, imagen_visualizer, veo3_animator
    print(f"--- Initializing FUSE: The Collaborative Brainstorming Intelligence (Project: {PROJECT_ID}) ---")

    # 1. Initialize State Manager (Redis)
    state_manager = SessionStateManager(host=REDIS_HOST)
    print(f"  State Manager (Redis) initialized at {REDIS_HOST}.")

    # 2. Initialize Proof Orchestrator (gemini-3.1-pro-preview)
    proof_orchestrator = ProofOrchestrator(project_id=PROJECT_ID, location=LOCATION)
    print("  Proof Orchestrator (gemini-3.1-pro-preview) initialized.")

    # 3. Initialize Vision Capture (gemini-3.1-flash-lite-preview) with two-pass pipeline
    vision_capture = VisionStateCapture(project_id=PROJECT_ID, state_manager=state_manager, location=LOCATION)
    print("  Vision State Capture (two-pass pipeline, gemini-3.1-flash-lite-preview) initialized.")

    # 4. Initialize Live Stream Handler (gemini-2.5-flash-native-audio-preview)
    live_handler = GeminiLiveStreamHandler(project_id=PROJECT_ID, state_manager=state_manager, location=LOCATION)
    print("  Gemini Live Stream Handler (Live API) initialized.")

    # 5. Initialize Diagram Renderer (Mermaid CLI)
    diagram_renderer = DiagramRenderer()
    print("  Diagram Renderer (Mermaid CLI) initialized.")

    # 6. Initialize Imagen Diagram Visualizer (imagen-4.0-generate-001)
    imagen_visualizer = ImagenDiagramVisualizer(
        project_id=PROJECT_ID, location=LOCATION, state_manager=state_manager
    )
    print("  Imagen Diagram Visualizer (imagen-4.0-generate-001) initialized.")

    # 7. Initialize Veo 3 Diagram Animator (veo-3.0-generate-preview)
    veo3_animator = Veo3DiagramAnimator(
        project_id=PROJECT_ID, location=LOCATION, state_manager=state_manager
    )
    print("  Veo3 Diagram Animator (veo-3.0-generate-preview) initialized.")

    print("\n--- System Ready ---")

    # Start periodic validation loop
    await run_periodic_validation(interval_seconds=60)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_agents())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
