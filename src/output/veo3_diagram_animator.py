"""Animates a photorealistic architecture image into a short walkthrough
video using Google Veo 3 via Vertex AI."""

import hashlib
import logging
import os
import time
from typing import Optional, Tuple

from google import genai
from google.genai import types

from src.state.session_state_manager import SessionStateManager

logger = logging.getLogger("fuse.veo3")

VEO3_POLL_TIMEOUT_SECONDS = 180  # Stop polling after 3 minutes
VEO3_POLL_INTERVAL_SECONDS = 5


class Veo3DiagramAnimator:
    """Animates a photorealistic architecture image into a short walkthrough
    video using Google Veo 3 via Vertex AI."""

    MODEL_ID = "veo-3.0-generate-preview"

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        state_manager: Optional[SessionStateManager] = None,
        output_dir: str = "output/animations",
    ):
        self.project_id = project_id
        self.location = "us-central1" if location == "global" else location
        self.state_manager = state_manager
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=self.location,
        )

        # Cache: image_hash -> (video_bytes, timestamp)
        self._cache: dict[str, Tuple[bytes, float]] = {}
        self._cache_ttl = 600  # 10 minutes

    def _hash_image(self, image_bytes: bytes) -> str:
        return hashlib.sha256(image_bytes).hexdigest()[:16]

    def _get_cached(self, image_hash: str) -> Optional[bytes]:
        if image_hash in self._cache:
            video_bytes, ts = self._cache[image_hash]
            if time.time() - ts < self._cache_ttl:
                logger.info("Veo3 cache hit for hash %s", image_hash)
                return video_bytes
            else:
                del self._cache[image_hash]
        return None

    def build_animation_prompt(self, mermaid_code: str = "") -> str:
        """Constructs an animation prompt describing camera movement and
        data-flow visualization for the architecture scene."""
        base_prompt = (
            "Smooth cinematic camera movement starting from a wide establishing shot, "
            "slowly dollying in toward the center of the infrastructure. "
            "Glowing data packets flow along the connections between components, "
            "pulsing with activity. Subtle particle effects emanate from active nodes. "
            "The camera gently orbits 15 degrees to reveal depth and layering. "
            "Ambient atmospheric lighting shifts subtly from cool blue to warm gold "
            "to convey the passage of data through the system. "
            "Photorealistic quality, 24fps, shallow depth of field."
        )

        if mermaid_code:
            mc_lower = mermaid_code.lower()
            if "database" in mc_lower or "db" in mc_lower:
                base_prompt += (
                    " Database cylinders emit a soft glow as queries arrive. "
                    "Read/write indicators pulse on the storage surfaces."
                )
            if "load" in mc_lower and "balancer" in mc_lower:
                base_prompt += (
                    " The load balancer distributes glowing request orbs "
                    "across the downstream servers in a fan-out pattern."
                )
            if "queue" in mc_lower or "kafka" in mc_lower:
                base_prompt += (
                    " Message queue pipelines show a conveyor-belt-like flow "
                    "of data packets moving steadily between producers and consumers."
                )
            if "cache" in mc_lower or "redis" in mc_lower:
                base_prompt += (
                    " The cache layer glows brightly with instant-access highlights, "
                    "contrasting with the deeper, slower storage behind it."
                )

        return base_prompt

    async def animate(
        self,
        image_bytes: bytes,
        mermaid_code: str = "",
        duration_seconds: int = 6,
    ) -> Optional[bytes]:
        """Generate an animated video from a photorealistic architecture image.
        Returns MP4 video bytes or None on failure."""
        if not image_bytes:
            logger.warning("No image bytes provided for animation.")
            return None

        image_hash = self._hash_image(image_bytes)

        # Check cache
        cached = self._get_cached(image_hash)
        if cached is not None:
            return cached

        animation_prompt = self.build_animation_prompt(mermaid_code)
        logger.info("Animation prompt (%d chars): %s...", len(animation_prompt), animation_prompt[:120])

        try:
            operation = self.client.models.generate_videos(
                model=self.MODEL_ID,
                prompt=animation_prompt,
                image=types.Image(image_bytes=image_bytes, mime_type="image/png"),
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9",
                    number_of_videos=1,
                    duration_seconds=duration_seconds,
                    person_generation="dont_allow",
                ),
            )

            # Poll until complete or timeout
            logger.info("Veo3 generation started. Polling for completion...")
            elapsed = 0
            while not operation.done:
                if elapsed >= VEO3_POLL_TIMEOUT_SECONDS:
                    logger.error("Veo3 polling timed out after %ds", elapsed)
                    return None
                time.sleep(VEO3_POLL_INTERVAL_SECONDS)
                elapsed += VEO3_POLL_INTERVAL_SECONDS
                operation = self.client.operations.get(operation)

            if operation.response and operation.response.generated_videos:
                video = operation.response.generated_videos[0]
                video_bytes = video.video.video_bytes

                # Cache
                self._cache[image_hash] = (video_bytes, time.time())

                # Persist to disk
                output_path = os.path.join(self.output_dir, f"animation_{image_hash}.mp4")
                with open(output_path, "wb") as f:
                    f.write(video_bytes)
                logger.info("Veo3 video saved to %s (%d bytes)", output_path, len(video_bytes))

                # Log event
                if self.state_manager:
                    self.state_manager.log_event("veo3_animation", {
                        "image_hash": image_hash,
                        "video_size": len(video_bytes),
                        "duration": duration_seconds,
                        "output_path": output_path,
                    })

                return video_bytes
            else:
                logger.error("Veo3 returned no videos. Operation: %s", operation)
                return None

        except Exception as e:
            logger.error("Veo3 animation failed: %s", e)
            return None

    def get_latest_video_path(self, image_bytes: bytes) -> Optional[str]:
        """Return the file path of a previously generated animation."""
        image_hash = self._hash_image(image_bytes)
        path = os.path.join(self.output_dir, f"animation_{image_hash}.mp4")
        return path if os.path.exists(path) else None
