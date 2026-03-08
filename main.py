import asyncio
import os
import signal
import sys
import threading
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import uvicorn
import json
from src.vision.vision_state_capture import VisionStateCapture
from src.audio.gemini_live_stream_handler import GeminiLiveStreamHandler
from src.state.session_state_manager import SessionStateManager
from src.agents.proof_orchestrator import ProofOrchestrator
from src.output.diagram_renderer import DiagramRenderer

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID", "fuse-489616")
LOCATION = os.getenv("LOCATION", "us-central1")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

# Global handlers for API access
live_handler = None
diagram_renderer = None
state_manager = None
vision_capture = None

# Initialize FastAPI app
app = FastAPI(title="FUSE: Collaborative Brainstorming Intelligence API")

@app.get("/")
async def health_check():
    return {"status": "active", "system": "FUSE", "project_id": PROJECT_ID}

@app.post("/command")
async def trigger_command(text: str):
    """Triggers a simulated voice command."""
    if not live_handler:
        return {"status": "error", "message": "Handler not initialized."}
    
    response = await live_handler.process_simulated_command(text)
    return {"status": "success", "response": response}

@app.post("/vision/frame")
async def receive_frame(request: Request):
    """Receives a binary image frame from the client-side streamer."""
    if not vision_capture:
        return {"status": "error", "message": "Vision capture not initialized."}
    
    frame_bytes = await request.body()
    if not frame_bytes:
        return {"status": "error", "message": "No frame data received."}
    
    mermaid_code = vision_capture.process_received_frame(frame_bytes)
    return {"status": "success", "mermaid_length": len(mermaid_code)}

@app.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles bidirectional multimodal streaming (Audio/Vision/Text).
    Connects the client directly to the Gemini 3.1 Flash Live session.
    """
    if not live_handler:
        await websocket.close(code=1011)
        return

    await websocket.accept()
    print("WebSocket connection established.")

    # Start the Gemini Live session in the background for this connection
    # and pipe data between the client and Gemini.
    try:
        async with live_handler.client.aio.live.connect(
            model=live_handler.model_id,
            config=live_handler.get_config()
        ) as session:
            
            async def receive_from_client():
                try:
                    while True:
                        message = await websocket.receive()
                        if "bytes" in message:
                            # Forward audio/vision bytes to Gemini
                            await session.send(input=message["bytes"], end_of_turn=False)
                        elif "text" in message:
                            # Forward text commands to Gemini
                            await session.send(input=message["text"], end_of_turn=True)
                except WebSocketDisconnect:
                    pass

            async def send_to_client():
                try:
                    async for response in session:
                        if response.text:
                            await websocket.send_text(json.dumps({"text": response.text}))
                        if response.audio:
                            await websocket.send_bytes(response.audio)
                except Exception as e:
                    print(f"Error sending to client: {e}")

            # Run both directions concurrently
            await asyncio.gather(receive_from_client(), send_to_client())

    except Exception as e:
        print(f"Live session error: {e}")
    finally:
        print("WebSocket connection closed.")

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

async def start_agents():
    global live_handler, diagram_renderer, state_manager, vision_capture
    print(f"--- Initializing FUSE: The Collaborative Brainstorming Intelligence (Project: {PROJECT_ID}) ---")
    
    # 1. Initialize State Manager (Redis)
    state_manager = SessionStateManager(host=REDIS_HOST)
    print(f"✓ Session State Manager (Redis) initialized at {REDIS_HOST}.")

    # 2. Initialize Proof Orchestrator (Gemini 3.1 Pro)
    po = ProofOrchestrator(project_id=PROJECT_ID, location=LOCATION)
    print("✓ Proof Orchestrator (Gemini 3.1 Pro) initialized.")

    # 3. Initialize Vision Capture (gemini-3.1-flash-lite-preview)
    vision_capture = VisionStateCapture(project_id=PROJECT_ID, state_manager=state_manager, location=LOCATION)
    print("✓ Vision State Capture (gemini-3.1-flash-lite-preview) initialized.")

    # 4. Initialize Live Stream Handler (Gemini 3.1 Flash Live)
    live_handler = GeminiLiveStreamHandler(project_id=PROJECT_ID, state_manager=state_manager, location=LOCATION)
    print("✓ Gemini Live Stream Handler (Gemini 3.1 Flash Live) initialized.")

    # 5. Initialize Diagram Renderer (Mermaid CLI)
    diagram_renderer = DiagramRenderer()
    print("✓ Diagram Renderer (Mermaid CLI) initialized.")

    print("\n--- System Ready ---")
    
    while True:
        await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_agents())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
