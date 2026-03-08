import os
import time
import cv2
import base64
from typing import List, Dict, Any
from google import genai
from google.genai import types

class VisionStateCapture:
    """
    Captures vision frames at 2-5 FPS and uses gemini-3.1-flash-lite-preview
    for low-latency OCR and extraction of architectural state.
    """
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.client = genai.Client(vertexai=True, project=project_id, location=location)
        self.model_id = "gemini-3.1-flash-lite-preview"
        
    def capture_and_analyze(self, video_source=0, fps=2):
        """
        Main loop for capturing frames and analyzing them.
        """
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            raise IOError("Cannot open webcam")
        
        last_frame_time = 0
        interval = 1.0 / fps
        
        try:
            while True:
                current_time = time.time()
                if current_time - last_frame_time >= interval:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Process frame
                    analysis = self._analyze_frame(frame)
                    print(f"Analysis: {analysis}")
                    
                    last_frame_time = current_time
                    
                # Small sleep to prevent 100% CPU usage
                time.sleep(0.01)
        finally:
            cap.release()

    def _analyze_frame(self, frame) -> str:
        """
        Sends frame to Gemini for analysis.
        """
        # Encode frame to base64
        _, buffer = cv2.imencode('.jpg', frame)
        encoded_image = base64.b64encode(buffer).decode('utf-8')
        
        prompt = (
            "Analyze this whiteboard image. Extract all technical nodes (boxes) and "
            "relationships (arrows). Output as a structured list of components and edges."
        )
        
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=base64.b64decode(encoded_image), mime_type="image/jpeg")
                    ]
                )
            ]
        )
        
        return response.text

if __name__ == "__main__":
    # Placeholder for project-id
    # vsc = VisionStateCapture(project_id="fuse-489616")
    # vsc.capture_and_analyze()
    pass
