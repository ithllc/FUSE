import time
from google import genai
from google.genai import types

from src.state.session_state_manager import SessionStateManager
from src.vision.scene_classifier import SceneClassifier, crop_to_roi
from src.vision.vision_prompts import (
    WHITEBOARD_PROMPT,
    IMAGINE_PROMPT,
    CHARADES_PROMPT,
    GENERIC_FALLBACK_PROMPT,
    build_context_block,
)


class VisionStateCapture:
    """
    Two-pass vision pipeline for FUSE:
      Pass 1 — Scene classification with bounding box detection
      Pass 2 — Mode-specific extraction with context injection
    """

    def __init__(self, project_id: str, state_manager: SessionStateManager, location: str = "global"):
        self.project_id = project_id
        self.location = location
        self.state_manager = state_manager
        self.client = genai.Client(vertexai=True, project=project_id, location=location)
        self.model_id = "gemini-3.1-flash-lite-preview"
        self.scene_classifier = SceneClassifier(self.client, self.model_id)

        # Scene classification cache (Phase 4)
        self._cached_scene = None
        self._cache_hits = 0
        self._cache_max = 5  # Re-classify after 5 consecutive cache hits

    def process_received_frame(self, frame_bytes: bytes) -> str:
        """Processes a frame through the two-pass vision pipeline."""
        t_start = time.time()

        # 1. Determine vision mode
        vision_mode = self.state_manager.get_vision_mode()

        # 2. Pass 1: Scene classification (skip if mode is explicit)
        if vision_mode == "auto":
            if self._cached_scene and self._cache_hits < self._cache_max:
                scene_type = self._cached_scene["scene_type"]
                bbox = self._cached_scene.get("bounding_box")
                confidence = self._cached_scene.get("confidence", 0.0)
                self._cache_hits += 1
            else:
                classification = self.scene_classifier.classify(frame_bytes)
                scene_type = classification["scene_type"]
                bbox = classification.get("bounding_box")
                confidence = classification.get("confidence", 0.0)
                self._cached_scene = classification
                self._cache_hits = 0
        else:
            scene_type = vision_mode
            bbox = None
            confidence = 1.0

        # 3. ROI crop if bounding box available and confidence is sufficient
        if bbox and confidence >= 0.6:
            cropped = crop_to_roi(frame_bytes, bbox, confidence=confidence)
        else:
            cropped = frame_bytes

        # 4. Build mode-specific prompt with context injection
        prompt = self._build_prompt(scene_type)

        # 5. Pass 2: Extract with mode-specific prompt
        mermaid_code = self._extract(cropped, prompt)

        # 6. Merge heuristic: avoid replacing a rich diagram with a partial view
        if mermaid_code:
            existing = self.state_manager.get_architectural_state()
            mermaid_code = self._merge_or_replace(mermaid_code, existing)
            self.state_manager.update_architectural_state(mermaid_code)
            elapsed_ms = int((time.time() - t_start) * 1000)
            self.state_manager.log_event("vision_update", {
                "scene_type": scene_type,
                "confidence": confidence,
                "cropped": bbox is not None,
                "mermaid_length": len(mermaid_code),
                "latency_ms": elapsed_ms,
            })

        return mermaid_code

    def _build_prompt(self, scene_type: str) -> str:
        """Builds a mode-specific prompt with injected session context."""
        context = build_context_block(self.state_manager.get_architectural_state())

        if scene_type == "whiteboard":
            return WHITEBOARD_PROMPT.format(context_block=context)
        elif scene_type in ("objects", "imagine"):
            registry = self.state_manager.get_proxy_registry()
            registry_str = (
                "\n".join(f"- {obj} -> {role}" for obj, role in registry.items())
                or "No objects assigned yet."
            )
            return IMAGINE_PROMPT.format(proxy_registry=registry_str, context_block=context)
        elif scene_type in ("gesture", "charades"):
            transcript = self.state_manager.get_recent_transcript(limit=5)
            return CHARADES_PROMPT.format(
                transcript_excerpt=transcript or "No recent voice context.",
                context_block=context,
            )
        else:
            return GENERIC_FALLBACK_PROMPT.format(context_block=context)

    def _extract(self, frame_bytes: bytes, prompt: str) -> str:
        """Pass 2: Sends cropped frame + mode-specific prompt to Gemini."""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt),
                            types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg"),
                        ],
                    )
                ],
            )
            text = response.text.strip() if response.text else ""
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return text
        except Exception as e:
            print(f"Vision extraction error: {e}")
            return ""

    def _merge_or_replace(self, new_mermaid: str, existing_mermaid: str) -> str:
        """If new output has far fewer connections than existing, keep existing."""
        if not existing_mermaid:
            return new_mermaid
        new_edges = len([l for l in new_mermaid.split("\n") if "-->" in l or "---" in l])
        existing_edges = len([l for l in existing_mermaid.split("\n") if "-->" in l or "---" in l])
        if existing_edges > 0 and new_edges < existing_edges * 0.5:
            return existing_mermaid
        return new_mermaid


if __name__ == "__main__":
    pass
