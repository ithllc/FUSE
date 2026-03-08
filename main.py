import asyncio
import os
import signal
import sys
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
from src.vision.vision_state_capture import VisionStateCapture
from src.audio.gemini_live_stream_handler import GeminiLiveStreamHandler
from src.state.session_state_manager import SessionStateManager
from src.agents.proof_orchestrator import ProofOrchestrator

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID", "fuse-489616")
LOCATION = os.getenv("LOCATION", "us-central1")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

# Initialize FastAPI app
app = FastAPI(title="FUSE: Collaborative Brainstorming Intelligence API")

@app.get("/")
async def health_check():
    return {"status": "active", "system": "FUSE", "project_id": PROJECT_ID}

async def start_agents():
    print(f"--- Initializing FUSE: The Collaborative Brainstorming Intelligence (Project: {PROJECT_ID}) ---")
    
    # 1. Initialize State Manager (Redis)
    sm = SessionStateManager(host=REDIS_HOST)
    print(f"✓ Session State Manager (Redis) initialized at {REDIS_HOST}.")

    # 2. Initialize Proof Orchestrator (Gemini 3.1 Pro)
    po = ProofOrchestrator(project_id=PROJECT_ID, location=LOCATION)
    print("✓ Proof Orchestrator (Gemini 3.1 Pro) initialized.")

    # 3. Initialize Vision Capture (gemini-3.1-flash-lite-preview)
    vsc = VisionStateCapture(project_id=PROJECT_ID, location=LOCATION)
    print("✓ Vision State Capture (gemini-3.1-flash-lite-preview) initialized.")

    # 4. Initialize Live Stream Handler (Gemini 3.1 Flash Live)
    lsh = GeminiLiveStreamHandler(project_id=PROJECT_ID, location=LOCATION)
    print("✓ Gemini Live Stream Handler (Gemini 3.1 Flash Live) initialized.")

    print("\n--- System Ready ---")
    
    # Placeholder for the main loop to keep agents active in the background
    while True:
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    # Start the agent orchestration in the background
    asyncio.create_task(start_agents())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
