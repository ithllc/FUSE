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

# Latest camera frame buffer for on-demand capture via Live API function calls (issue #19)
_latest_frame: Optional[bytes] = None

# Video streaming state for observability (issue #22)
_video_streaming = False
_video_frames_sent = 0
_video_last_error = None


def _resize_frame_for_live_api(frame_bytes: bytes) -> bytes:
    """Resize frame to 768x768 JPEG quality 70 for Gemini Live API video input (issue #22)."""
    import cv2
    import numpy as np
    try:
        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return frame_bytes
        img = cv2.resize(img, (768, 768), interpolation=cv2.INTER_AREA)
        _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return buf.tobytes()
    except Exception:
        return frame_bytes

# Initialize FastAPI app
app = FastAPI(title="FUSE: Collaborative Brainstorming Intelligence API")

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serves the FUSE web interface."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/healthz")
async def healthz():
    """Lightweight liveness probe — no downstream checks."""
    return {"status": "ok"}

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

    # 3. Video streaming is part of the Gemini Live API component (not a separate
    #    component). Its status is reported via WebSocket video_status messages.
    #    Removed from /health to avoid false "Unknown error" in component panel (issue #24).

    # 4. Session state summary
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
    global _processing_frame, _latest_frame

    if not vision_capture:
        return {"status": "error", "message": "Vision capture not initialized."}

    # Frame debounce: skip if previous frame still processing
    if _processing_frame:
        return {"status": "skipped", "reason": "Previous frame still processing"}

    frame_bytes = await request.body()
    if not frame_bytes:
        return {"status": "error", "message": "No frame data received."}

    # Buffer latest frame for on-demand capture via Live API function calls (issue #19)
    _latest_frame = frame_bytes

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

    # Session resumption state (issue #18)
    resumption_handle = None
    # Track whether this is the first Gemini connection (show diagnostics only once)
    first_connect = True
    # Client-level flag: True while the browser WebSocket is alive
    client_connected = True
    MAX_RECONNECTS = 10

    try:
        # Stage: connecting to Gemini
        await websocket.send_text(json.dumps({
            "type": "status",
            "stage": "connecting",
            "message": "Connecting to Gemini Live API..."
        }))

        reconnect_count = 0

        # --- Gemini reconnect loop (issue #18) ---
        # The Gemini Live API may end sessions after turn completion, GoAway,
        # or server-side resets. When this happens, we reconnect transparently
        # using the saved resumption handle. The client WebSocket stays open.
        while client_connected and reconnect_count < MAX_RECONNECTS:
            try:
                config = live_handler.get_config(resumption_handle=resumption_handle)
                async with live_handler.client.aio.live.connect(
                    model=live_handler.model_id,
                    config=config
                ) as session:
                    if first_connect:
                        logger.info("Gemini Live session connected successfully.")
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "stage": "connected",
                            "message": "Live session active. Running diagnostics...",
                            "model": live_handler.model_id,
                            "location": live_handler.location
                        }))
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "stage": "diagnostics",
                            "message": "Running pre-session diagnostics..."
                        }))
                        first_connect = False
                    else:
                        logger.info(f"Gemini Live session reconnected (attempt {reconnect_count}, handle={'yes' if resumption_handle else 'no'}).")
                        await websocket.send_text(json.dumps({
                            "type": "status",
                            "stage": "reconnected",
                            "message": "Audio session reconnected."
                        }))

                    # Shared flag so tasks can signal each other to stop
                    session_active = True
                    # Flag set by GoAway handler to trigger clean reconnect
                    needs_reconnect = False

                    async def keepalive_ping():
                        """Send periodic keepalive pings to prevent Cloud Run LB timeout (issue #20)."""
                        try:
                            while session_active and client_connected:
                                await asyncio.sleep(15)
                                if session_active and client_connected:
                                    try:
                                        await websocket.send_text(json.dumps({"type": "ping", "ts": int(time.time())}))
                                    except Exception:
                                        break
                        except asyncio.CancelledError:
                            pass

                    async def _execute_tool_call(fc) -> dict:
                        """Execute a function call from Gemini and return the result.

                        Handles: capture_and_analyze_frame, get_session_context,
                        set_proxy_object. All calls are logged to Redis for audit trail.
                        (issue #19)
                        """
                        t0 = time.time()
                        func_name = fc.name
                        func_args = dict(fc.args) if fc.args else {}
                        call_id = fc.id

                        # Audit: log the tool call
                        if state_manager:
                            state_manager.log_event("tool_call", {
                                "function": func_name,
                                "arguments": func_args,
                                "call_id": call_id,
                            })
                        logger.info(f"Tool call: {func_name}({func_args}) [id={call_id}]")

                        result = {}
                        try:
                            if func_name == "capture_and_analyze_frame":
                                mode = func_args.get("mode", "auto")
                                if _latest_frame and vision_capture:
                                    # Apply mode override
                                    if mode != "auto" and state_manager:
                                        state_manager.set_vision_mode(mode)
                                    mermaid_code = vision_capture.process_received_frame(_latest_frame)
                                    scene_type = vision_capture._cached_scene.get("scene_type", "unknown") if vision_capture._cached_scene else "unknown"
                                    result = {
                                        "status": "success",
                                        "scene_type": scene_type,
                                        "mermaid_code": mermaid_code[:500] if mermaid_code else None,
                                        "mermaid_length": len(mermaid_code) if mermaid_code else 0,
                                        "description": f"Captured and analyzed frame in {mode} mode. Scene type: {scene_type}.",
                                    }
                                else:
                                    result = {
                                        "status": "no_frame",
                                        "description": "No camera frame available. The camera may not be active.",
                                    }

                            elif func_name == "get_session_context":
                                if state_manager:
                                    proxies = state_manager.get_proxy_registry()
                                    mermaid = state_manager.get_architectural_state()
                                    transcript = state_manager.get_recent_transcript(limit=5)
                                    mode = state_manager.get_vision_mode()
                                    result = {
                                        "status": "success",
                                        "proxy_objects": proxies if proxies else "No objects assigned yet.",
                                        "current_diagram": mermaid[:500] if mermaid else "No diagram yet.",
                                        "diagram_length": len(mermaid) if mermaid else 0,
                                        "recent_transcript": transcript or "No recent transcript.",
                                        "vision_mode": mode,
                                    }
                                else:
                                    result = {"status": "error", "description": "State manager not available."}

                            elif func_name == "set_proxy_object":
                                obj = func_args.get("object_name", "")
                                role = func_args.get("technical_role", "")
                                if obj and role and state_manager:
                                    state_manager.set_object_proxy(obj, role)
                                    state_manager.log_event("proxy_assignment", {"object": obj, "role": role})
                                    logger.info(f"Proxy registered via tool call: {obj} -> {role}")
                                    result = {
                                        "status": "success",
                                        "description": f"Registered {obj} as {role}.",
                                        "proxy_registry": state_manager.get_proxy_registry(),
                                    }
                                    # Notify client of proxy update
                                    await websocket.send_text(json.dumps({
                                        "type": "command_result",
                                        "text": f"Registered: {obj} → {role}",
                                        "proxies": state_manager.get_proxy_registry(),
                                    }))
                                else:
                                    result = {"status": "error", "description": "Missing object_name or technical_role."}

                            else:
                                result = {"status": "error", "description": f"Unknown function: {func_name}"}

                        except Exception as e:
                            logger.error(f"Tool call error ({func_name}): {e}")
                            result = {"status": "error", "description": str(e)}

                        # Audit: log the tool response
                        elapsed_ms = int((time.time() - t0) * 1000)
                        if state_manager:
                            state_manager.log_event("tool_response", {
                                "function": func_name,
                                "call_id": call_id,
                                "status": result.get("status", "unknown"),
                                "latency_ms": elapsed_ms,
                            })
                        logger.info(f"Tool response: {func_name} -> {result.get('status')} ({elapsed_ms}ms)")

                        # Notify client of tool activity
                        await websocket.send_text(json.dumps({
                            "type": "tool_activity",
                            "function": func_name,
                            "status": result.get("status", "unknown"),
                            "latency_ms": elapsed_ms,
                        }))

                        return result

                    async def _check_voice_commands(text: str):
                        """Parse transcribed speech for proxy and mode commands."""
                        if not state_manager:
                            return
                        result = await live_handler.process_simulated_command(text)
                        if result and result != "Command not recognized.":
                            logger.info(f"Voice command detected: {result}")
                            await websocket.send_text(json.dumps({
                                "type": "command_result",
                                "text": result,
                                "proxies": state_manager.get_proxy_registry()
                            }))

                    async def video_sender():
                        """Send camera frames to Gemini Live API at 1 FPS for visual awareness (issue #22)."""
                        global _video_streaming, _video_frames_sent, _video_last_error
                        try:
                            _video_streaming = True
                            _video_frames_sent = 0
                            _video_last_error = None

                            # Notify client that video streaming started
                            await websocket.send_text(json.dumps({
                                "type": "video_status",
                                "status": "streaming",
                                "message": "VIDEO: Streaming at 1 FPS (768x768)"
                            }))
                            logger.info("VIDEO: Streaming started (1 FPS, 768x768)")

                            while session_active and client_connected:
                                await asyncio.sleep(1.0)  # 1 FPS

                                if not session_active or not client_connected:
                                    break

                                # A/B test toggle: skip sending video to Gemini when disabled (issue #26)
                                if not _video_to_gemini_enabled:
                                    continue

                                frame = _latest_frame
                                if frame is None:
                                    continue

                                try:
                                    resized = _resize_frame_for_live_api(frame)
                                    video_blob = genai_types.Blob(
                                        data=resized,
                                        mime_type="image/jpeg"
                                    )
                                    await session.send_realtime_input(video=video_blob)
                                    _video_frames_sent += 1

                                    # Log every 30 frames (30 seconds)
                                    if _video_frames_sent % 30 == 0:
                                        logger.info(f"VIDEO: {_video_frames_sent} frames sent")
                                        await websocket.send_text(json.dumps({
                                            "type": "video_status",
                                            "status": "streaming",
                                            "frames_sent": _video_frames_sent
                                        }))

                                except Exception as e:
                                    _video_last_error = str(e)
                                    logger.warning(f"VIDEO: Frame send failed — {e}")

                        except asyncio.CancelledError:
                            pass
                        finally:
                            _video_streaming = False
                            logger.info(f"VIDEO: Streaming stopped ({_video_frames_sent} frames sent)")

                    # A/B test: video-to-gemini toggle (issue #26)
                    # Default OFF — continuous video frames cause Gemini audio stalls
                    # (17s+ delays after ~10 exchanges). Use on-demand function calling instead.
                    _video_to_gemini_enabled = False

                    # Latency instrumentation state (issue #25)
                    _latency_samples = []
                    _last_audio_recv_ts = 0.0  # when server last received audio from client
                    _last_audio_to_gemini_ts = 0.0  # when server last sent audio to Gemini
                    _audio_exchange_count = 0

                    async def receive_from_client():
                        nonlocal session_active, client_connected
                        nonlocal _last_audio_recv_ts, _last_audio_to_gemini_ts
                        global _latest_frame
                        try:
                            while session_active:
                                message = await websocket.receive()
                                if "bytes" in message:
                                    raw = message["bytes"]
                                    # Check for video frame prefix 'V' (0x56) — issue #22
                                    if len(raw) > 1 and raw[0:1] == b'V':
                                        # Video frame — update latest frame buffer
                                        _latest_frame = raw[1:]
                                    else:
                                        # Audio frame — send to Gemini Live API
                                        _last_audio_recv_ts = time.time()  # issue #25
                                        audio_blob = genai_types.Blob(
                                            data=raw,
                                            mime_type="audio/pcm;rate=16000"
                                        )
                                        await session.send_realtime_input(audio=audio_blob)
                                        _last_audio_to_gemini_ts = time.time()  # issue #25
                                elif "text" in message:
                                    raw = message["text"]
                                    try:
                                        parsed = json.loads(raw)
                                        # A/B test: handle video toggle command (issue #26)
                                        if isinstance(parsed, dict) and parsed.get("type") == "video_toggle":
                                            _video_to_gemini_enabled = parsed.get("enabled", True)
                                            mode = "ON (audio+video)" if _video_to_gemini_enabled else "OFF (audio only)"
                                            logger.info(f"A/B TEST: Video to Gemini {mode}")
                                            await websocket.send_text(json.dumps({
                                                "type": "video_toggle_ack",
                                                "enabled": _video_to_gemini_enabled,
                                                "message": f"Video streaming to Gemini: {mode}"
                                            }))
                                            continue
                                        text_val = parsed.get("text", raw) if isinstance(parsed, dict) else raw
                                    except (json.JSONDecodeError, TypeError):
                                        text_val = raw
                                    if state_manager:
                                        state_manager.log_event("voice_input", {"text": text_val})
                                    # Use send_realtime_input for text (issue #18)
                                    # Deprecated session.send() causes sessions to go
                                    # unresponsive after first turn_complete (python-genai #1224)
                                    await session.send_realtime_input(text=text_val)
                        except WebSocketDisconnect:
                            logger.info("Client disconnected from WebSocket.")
                            client_connected = False
                        except Exception as e:
                            if session_active:
                                logger.error(f"Error in receive_from_client: {e}")
                            client_connected = False
                        finally:
                            session_active = False

                    async def send_to_client():
                        nonlocal session_active, needs_reconnect, resumption_handle
                        nonlocal _last_audio_recv_ts, _last_audio_to_gemini_ts, _audio_exchange_count
                        try:
                            async for response in session.receive():
                                if response is None:
                                    break

                                # Capture session resumption handle (issue #18)
                                if hasattr(response, 'session_resumption_update') and response.session_resumption_update:
                                    update = response.session_resumption_update
                                    if hasattr(update, 'new_handle') and update.new_handle:
                                        resumption_handle = update.new_handle
                                        logger.info("Session resumption handle updated.")

                                # Handle GoAway: Gemini server will close soon (issue #18)
                                if hasattr(response, 'go_away') and response.go_away is not None:
                                    time_left = getattr(response.go_away, 'time_left', 'unknown')
                                    logger.warning(f"Gemini GoAway received, time_left={time_left}. Will reconnect.")
                                    if state_manager:
                                        state_manager.log_event("gemini_goaway", {"time_left": str(time_left)})
                                    needs_reconnect = True
                                    break

                                # Handle function calls from Gemini (issue #19)
                                if hasattr(response, 'tool_call') and response.tool_call:
                                    function_responses = []
                                    for fc in response.tool_call.function_calls:
                                        result = await _execute_tool_call(fc)
                                        function_responses.append(
                                            genai_types.FunctionResponse(
                                                id=fc.id,
                                                name=fc.name,
                                                response=result,
                                            )
                                        )
                                    # Send function results back to Gemini
                                    await session.send_tool_response(
                                        function_responses=function_responses
                                    )
                                    continue

                                if hasattr(response, 'server_content') and response.server_content:
                                    sc = response.server_content

                                    # Input transcription (what the user said)
                                    if hasattr(sc, 'input_transcription') and sc.input_transcription:
                                        t = sc.input_transcription
                                        if hasattr(t, 'text') and t.text:
                                            await websocket.send_text(json.dumps({
                                                "type": "transcript",
                                                "role": "user",
                                                "text": t.text,
                                                "finished": getattr(t, 'finished', False)
                                            }))
                                            if state_manager and getattr(t, 'finished', False):
                                                state_manager.log_event("voice_input", {"text": t.text})
                                                await _check_voice_commands(t.text)

                                    # Output transcription (what Gemini said)
                                    if hasattr(sc, 'output_transcription') and sc.output_transcription:
                                        t = sc.output_transcription
                                        if hasattr(t, 'text') and t.text:
                                            await websocket.send_text(json.dumps({
                                                "type": "transcript",
                                                "role": "fuse",
                                                "text": t.text,
                                                "finished": getattr(t, 'finished', False)
                                            }))
                                            if state_manager and getattr(t, 'finished', False):
                                                state_manager.log_event("gemini_output", {"text": t.text})

                                    if hasattr(sc, 'model_turn') and sc.model_turn and sc.model_turn.parts:
                                        for part in sc.model_turn.parts:
                                            if hasattr(part, 'text') and part.text:
                                                await websocket.send_text(json.dumps({"text": part.text}))
                                                if state_manager:
                                                    state_manager.log_event("gemini_output", {"text": part.text})
                                            if hasattr(part, 'inline_data') and part.inline_data:
                                                # Latency instrumentation (issue #25)
                                                t_gemini_resp = time.time()
                                                await websocket.send_bytes(part.inline_data.data)
                                                t_sent = time.time()
                                                if _last_audio_recv_ts > 0:
                                                    _audio_exchange_count += 1
                                                    latency = {
                                                        "server_recv_to_gemini": round((_last_audio_to_gemini_ts - _last_audio_recv_ts) * 1000),
                                                        "gemini_processing": round((t_gemini_resp - _last_audio_to_gemini_ts) * 1000),
                                                        "server_to_client": round((t_sent - t_gemini_resp) * 1000),
                                                        "total_server": round((t_sent - _last_audio_recv_ts) * 1000),
                                                    }
                                                    # Send latency report every 10 audio exchanges
                                                    if _audio_exchange_count % 10 == 1 or _audio_exchange_count <= 3:
                                                        try:
                                                            await websocket.send_text(json.dumps({
                                                                "type": "latency",
                                                                "hop": "server",
                                                                "n": _audio_exchange_count,
                                                                **latency,
                                                            }))
                                                        except Exception:
                                                            pass
                                if hasattr(response, 'text') and response.text:
                                    await websocket.send_text(json.dumps({"text": response.text}))
                                if hasattr(response, 'data') and response.data:
                                    # Latency instrumentation (issue #25)
                                    t_gemini_resp = time.time()
                                    await websocket.send_bytes(response.data)
                                    t_sent = time.time()
                                    if _last_audio_recv_ts > 0:
                                        _audio_exchange_count += 1
                                        latency = {
                                            "server_recv_to_gemini": round((_last_audio_to_gemini_ts - _last_audio_recv_ts) * 1000),
                                            "gemini_processing": round((t_gemini_resp - _last_audio_to_gemini_ts) * 1000),
                                            "server_to_client": round((t_sent - t_gemini_resp) * 1000),
                                            "total_server": round((t_sent - _last_audio_recv_ts) * 1000),
                                        }
                                        if _audio_exchange_count % 10 == 1 or _audio_exchange_count <= 3:
                                            try:
                                                await websocket.send_text(json.dumps({
                                                    "type": "latency",
                                                    "hop": "server",
                                                    "n": _audio_exchange_count,
                                                    **latency,
                                                }))
                                            except Exception:
                                                pass
                        except Exception as e:
                            error_str = str(e)
                            if "1000" in error_str:
                                logger.info("Gemini Live session ended normally (code 1000). Will reconnect.")
                                needs_reconnect = True
                            else:
                                logger.error(f"Error in send_to_client: {e}\n{traceback.format_exc()}")
                                needs_reconnect = True
                        finally:
                            session_active = False

                    # Run all four tasks; when send or receive finishes, cancel the others
                    tasks = [
                        asyncio.create_task(receive_from_client()),
                        asyncio.create_task(send_to_client()),
                        asyncio.create_task(keepalive_ping()),
                        asyncio.create_task(video_sender()),
                    ]

                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                # After exiting async with, decide: reconnect or exit
                if not client_connected:
                    logger.info("Client disconnected, stopping reconnect loop.")
                    break

                if needs_reconnect:
                    reconnect_count += 1
                    logger.info(f"Reconnecting Gemini session ({reconnect_count}/{MAX_RECONNECTS})...")
                    await asyncio.sleep(0.5)
                    continue

                # session.receive() ended without GoAway or error — reconnect anyway
                reconnect_count += 1
                logger.info(f"Gemini receive loop ended, reconnecting ({reconnect_count}/{MAX_RECONNECTS})...")
                await asyncio.sleep(0.5)

            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                logger.error(f"Gemini connect error (attempt {reconnect_count}): {error_msg}\n{traceback.format_exc()}")
                reconnect_count += 1
                if reconnect_count >= MAX_RECONNECTS or not client_connected:
                    break
                await asyncio.sleep(1.0)

        if reconnect_count >= MAX_RECONNECTS:
            logger.error(f"Max Gemini reconnects ({MAX_RECONNECTS}) reached. Closing WebSocket.")

    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        logger.error(f"Live session error at stage 'gemini_connect': {error_msg}\n{traceback.format_exc()}")

        if state_manager:
            state_manager.log_event("connection_error", {
                "stage": "gemini_connect",
                "error_type": type(e).__name__,
                "detail": str(e),
            })

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
        # Send proper close frame so client sees 1000 instead of 1006 (issue #18)
        try:
            await websocket.close(code=1000, reason="Session ended")
        except Exception:
            pass
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
    """Initialize all FUSE components. Awaited at startup so Cloud Run readiness
    probe does not pass until handlers are ready (fixes cold-start issue #23)."""
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

@app.on_event("startup")
async def startup_event():
    # Await initialization so the server does not accept requests until all
    # handlers are ready. This prevents the 2-minute cold-start delay where
    # clients connect but get "InitializationError" rejections (issue #23).
    await start_agents()
    # Periodic validation runs in the background — does not block readiness
    asyncio.create_task(run_periodic_validation(interval_seconds=60))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
