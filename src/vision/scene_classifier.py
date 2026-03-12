import json
import numpy as np
import cv2
from google.genai import types


class SceneClassifier:
    """Pass 1: Classifies what the camera sees and returns ROI bounding box."""

    CLASSIFICATION_PROMPT = (
        "Analyze this image and classify the primary subject. "
        "Return ONLY a JSON object with these fields:\n"
        '- "scene_type": one of "whiteboard", "objects", "gesture", "mixed", "unclear"\n'
        '- "bounding_box": [ymin, xmin, ymax, xmax] normalized 0-1000 for the focal region, or null if unclear\n'
        '- "confidence": float 0.0-1.0\n\n'
        'Example: {"scene_type": "whiteboard", "bounding_box": [100, 50, 900, 950], "confidence": 0.92}'
    )

    FALLBACK = {"scene_type": "unclear", "bounding_box": None, "confidence": 0.0}

    def __init__(self, client, model_id: str):
        self.client = client
        self.model_id = model_id

    def classify(self, frame_bytes: bytes) -> dict:
        """Returns {"scene_type": str, "bounding_box": list|None, "confidence": float}."""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=self.CLASSIFICATION_PROMPT),
                            types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg"),
                        ],
                    )
                ],
            )
            text = response.text.strip() if response.text else ""
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(text)
            # Validate required fields
            if result.get("scene_type") not in ("whiteboard", "objects", "gesture", "mixed", "unclear"):
                return dict(self.FALLBACK)
            return {
                "scene_type": result["scene_type"],
                "bounding_box": result.get("bounding_box"),
                "confidence": float(result.get("confidence", 0.0)),
            }
        except (json.JSONDecodeError, KeyError, TypeError, Exception) as e:
            print(f"Scene classification error: {e}")
            return dict(self.FALLBACK)


def crop_to_roi(frame_bytes: bytes, bounding_box: list, min_confidence: float = 0.6, confidence: float = 1.0) -> bytes:
    """Crops JPEG frame to bounding box region. Returns original if crop fails or confidence is low."""
    if confidence < min_confidence:
        return frame_bytes

    try:
        # Decode JPEG to numpy array
        nparr = np.frombuffer(frame_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return frame_bytes

        h, w = img.shape[:2]
        ymin, xmin, ymax, xmax = bounding_box

        # Descale from 0-1000 to pixel coordinates
        py_min = int(ymin * h / 1000)
        px_min = int(xmin * w / 1000)
        py_max = int(ymax * h / 1000)
        px_max = int(xmax * w / 1000)

        # Clamp to image bounds
        py_min = max(0, py_min)
        px_min = max(0, px_min)
        py_max = min(h, py_max)
        px_max = min(w, px_max)

        # Ensure non-zero crop area
        if py_max <= py_min or px_max <= px_min:
            return frame_bytes

        cropped = img[py_min:py_max, px_min:px_max]
        _, buf = cv2.imencode(".jpg", cropped, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes()
    except Exception as e:
        print(f"ROI crop error: {e}")
        return frame_bytes
