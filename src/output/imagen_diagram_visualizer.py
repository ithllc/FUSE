"""Converts Mermaid.js architecture diagrams into photorealistic images
using Google Imagen via the google-genai SDK on Vertex AI."""

import hashlib
import logging
import os
import time
from typing import Optional, Tuple

from google import genai
from google.genai import types

from src.output.mermaid_scene_translator import MermaidSceneTranslator
from src.state.session_state_manager import SessionStateManager

logger = logging.getLogger("fuse.imagen")


class ImagenDiagramVisualizer:
    """Generates photorealistic images from Mermaid.js architecture diagrams."""

    MODEL_ID = "imagen-4.0-generate-001"

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        state_manager: Optional[SessionStateManager] = None,
        output_dir: str = "output/visualizations",
    ):
        self.project_id = project_id
        # Imagen may not be available in "global"; default to us-central1
        self.location = "us-central1" if location == "global" else location
        self.state_manager = state_manager
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=self.location,
        )
        self.translator = MermaidSceneTranslator()

        # In-memory cache: mermaid_hash -> (image_bytes, timestamp)
        self._cache: dict[str, Tuple[bytes, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    def _hash_mermaid(self, mermaid_code: str) -> str:
        return hashlib.sha256(mermaid_code.strip().encode()).hexdigest()[:16]

    def _get_cached(self, mermaid_hash: str) -> Optional[bytes]:
        if mermaid_hash in self._cache:
            image_bytes, ts = self._cache[mermaid_hash]
            if time.time() - ts < self._cache_ttl:
                logger.info("Imagen cache hit for hash %s", mermaid_hash)
                return image_bytes
            else:
                del self._cache[mermaid_hash]
        return None

    async def generate(self, mermaid_code: str) -> Optional[bytes]:
        """Generate a photorealistic image from Mermaid.js code.
        Returns PNG image bytes or None on failure."""
        if not mermaid_code:
            logger.warning("No Mermaid code provided for visualization.")
            return None

        mermaid_hash = self._hash_mermaid(mermaid_code)

        # Check cache
        cached = self._get_cached(mermaid_hash)
        if cached is not None:
            return cached

        # Translate Mermaid to scene description
        scene_prompt = self.translator.translate(mermaid_code)
        logger.info("Scene prompt generated (%d chars): %s...", len(scene_prompt), scene_prompt[:120])

        full_prompt = (
            "Create a photorealistic, highly detailed architectural visualization. "
            "The scene depicts a modern technology infrastructure viewed from a "
            "slightly elevated isometric perspective with dramatic lighting. "
            f"{scene_prompt} "
            "Style: photorealistic CGI render, cinematic lighting, depth of field, "
            "8K detail, technical precision. No text labels or annotations."
        )

        try:
            response = self.client.models.generate_images(
                model=self.MODEL_ID,
                prompt=full_prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="16:9",
                    output_mime_type="image/png",
                ),
            )

            if response.generated_images and len(response.generated_images) > 0:
                image_bytes = response.generated_images[0].image.image_bytes
                # Cache the result
                self._cache[mermaid_hash] = (image_bytes, time.time())

                # Persist to disk
                output_path = os.path.join(self.output_dir, f"realistic_{mermaid_hash}.png")
                with open(output_path, "wb") as f:
                    f.write(image_bytes)
                logger.info("Imagen image saved to %s (%d bytes)", output_path, len(image_bytes))

                # Log event
                if self.state_manager:
                    self.state_manager.log_event("imagen_generation", {
                        "mermaid_hash": mermaid_hash,
                        "image_size": len(image_bytes),
                        "output_path": output_path,
                    })

                return image_bytes
            else:
                logger.error("Imagen returned no images.")
                return None

        except Exception as e:
            logger.error("Imagen generation failed: %s", e)
            return None

    def get_latest_image_path(self, mermaid_code: str) -> Optional[str]:
        """Return the file path to a previously generated image, if it exists on disk."""
        mermaid_hash = self._hash_mermaid(mermaid_code)
        path = os.path.join(self.output_dir, f"realistic_{mermaid_hash}.png")
        return path if os.path.exists(path) else None
