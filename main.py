import asyncio
import os
import signal
import sys
from dotenv import load_dotenv
from src.vision.vision_state_capture import VisionStateCapture
from src.audio.gemini_live_stream_handler import GeminiLiveStreamHandler
from src.state.session_state_manager import SessionStateManager
from src.agents.proof_orchestrator import ProofOrchestrator

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID", "fuse-489616")
LOCATION = os.getenv("LOCATION", "us-central1")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

async def main():
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
    print("To start the multimodal session, ensure your media inputs are configured.")
    
    # In a full implementation, these would run in parallel:
    # await asyncio.gather(
    #     lsh.start_session(),
    #     vsc.capture_and_analyze() # This might need its own thread/process due to CV2
    # )
    
    # Placeholder for the main loop to keep the script running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down FUSE...")

if __name__ == "__main__":
    asyncio.run(main())
