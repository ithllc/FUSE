import os
import time
import cv2
import base64
from typing import List, Dict, Any
from google import genai
from google.genai import types

from src.state.session_state_manager import SessionStateManager

class VisionStateCapture:
    """
    Captures vision frames at 2-5 FPS and uses gemini-3.1-flash-lite-preview
    for low-latency OCR and extraction of architectural state.
    """
    def __init__(self, project_id: str, state_manager: SessionStateManager, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.state_manager = state_manager
        self.client = genai.Client(vertexai=True, project=project_id, location=location)
        self.model_id = "gemini-3.1-flash-lite-preview"
        
    def process_received_frame(self, frame_bytes: bytes) -> str:
        """
        Processes a frame received from the client-side streamer.
        """
        prompt = (
            "Analyze this whiteboard image or technical sketch. "
            "Extract all technical nodes (boxes/components) and relationships (arrows/lines). "
            "Output ONLY the valid Mermaid.js 'graph TD' or 'graph LR' code representing the diagram. "
            "Do not include markdown code blocks or any other text."
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg")
                        ]
                    )
                ]
            )
            
            mermaid_code = response.text.strip()
            if mermaid_code:
                self.state_manager.update_architectural_state(mermaid_code)
                self.state_manager.log_event("vision_update", {"mermaid_length": len(mermaid_code)})
            
            return mermaid_code
        except Exception as e:
            print(f"Vision analysis error: {e}")
            return ""

if __name__ == "__main__":
    # Placeholder for project-id
    # vsc = VisionStateCapture(project_id="fuse-489616")
    # vsc.capture_and_analyze()
    pass
