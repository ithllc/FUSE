# Imagen + Veo 3 Diagram Visualization Feature

## 1. Feature Overview

This feature extends FUSE's diagram rendering pipeline to produce photorealistic visualizations and short animated videos from Mermaid.js architecture diagrams. The pipeline has three stages:

1. **Mermaid Parse** -- Extract nodes, edges, and subgraphs from the current Mermaid.js architectural state stored in Redis.
2. **Imagen Generation** -- Feed a structured scene-description prompt (derived from the parsed Mermaid graph) to Google Imagen via Vertex AI to produce a high-resolution photorealistic image of the architecture.
3. **Veo 3 Animation** -- Send the Imagen-generated image together with a camera/motion prompt to Google Veo 3 via Vertex AI to produce a 4-8 second MP4 walkthrough animation.

Both outputs (image and video) are served through new FastAPI endpoints and surfaced in the existing web UI with dedicated buttons and a media display area.

---

## 2. User Story

> As a brainstorming participant, I want to see my architecture come to life as a realistic visualization and animated walkthrough so that abstract box-and-arrow diagrams become tangible, memorable, and easier to discuss with non-technical stakeholders.

**Acceptance Criteria:**

- Clicking "Visualize" in the diagram panel generates a photorealistic image within 30 seconds and displays it inline.
- Clicking "Animate" takes the most recent realistic image and produces a short video within 120 seconds, displayed inline with playback controls.
- If the Mermaid state has not changed since the last generation, cached results are returned immediately.
- Errors from Imagen or Veo 3 display a clear message and fall back to the standard Mermaid SVG diagram.

---

## 3. Technical Design

### 3.1 New Components

| Component | File Path | Responsibility |
|---|---|---|
| `ImagenDiagramVisualizer` | `src/output/imagen_diagram_visualizer.py` | Parses Mermaid code, builds scene prompts, calls Imagen API, returns image bytes |
| `Veo3DiagramAnimator` | `src/output/veo3_diagram_animator.py` | Takes an image + animation prompt, calls Veo 3 API, returns video bytes |
| `MermaidSceneTranslator` | `src/output/mermaid_scene_translator.py` | Pure-logic module that converts parsed Mermaid AST into natural-language scene descriptions |

### 3.2 Integration with Existing Pipeline

```
SessionStateManager.get_architectural_state()
        |
        v
   Mermaid code (string)
        |
        +---> DiagramRenderer.render()           [existing -- Mermaid SVG/PNG]
        |
        +---> MermaidSceneTranslator.translate()  [new]
                    |
                    v
              Scene description (string)
                    |
                    +---> ImagenDiagramVisualizer.generate()  [new -- photorealistic PNG]
                                |
                                v
                          Image bytes
                                |
                                +---> Veo3DiagramAnimator.animate()  [new -- MP4 video]
```

### 3.3 Initialization in `main.py`

The new components are instantiated in `start_agents()` alongside the existing globals:

```python
# main.py additions (globals)
imagen_visualizer = None
veo3_animator = None

# Inside start_agents()
from src.output.imagen_diagram_visualizer import ImagenDiagramVisualizer
from src.output.veo3_diagram_animator import Veo3DiagramAnimator

imagen_visualizer = ImagenDiagramVisualizer(
    project_id=PROJECT_ID,
    location=LOCATION,
    state_manager=state_manager,
)
veo3_animator = Veo3DiagramAnimator(
    project_id=PROJECT_ID,
    location=LOCATION,
    state_manager=state_manager,
)
```

---

## 4. Imagen Integration

### 4.1 Model and SDK

- **Model**: `imagen-4.0-generate-001` (latest Imagen model on Vertex AI as of 2026-03)
- **SDK**: `google-genai` (already in `requirements.txt`)
- **Location**: `us-central1` (Imagen availability; falls back to project default)

### 4.2 ImagenDiagramVisualizer Implementation

```python
# src/output/imagen_diagram_visualizer.py

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
    """
    Converts Mermaid.js architecture diagrams into photorealistic images
    using Google Imagen via the google-genai SDK on Vertex AI.
    """

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
        """
        Generate a photorealistic image from Mermaid.js code.

        Returns PNG image bytes or None on failure.
        """
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
        """
        Return the file path to a previously generated image for the given
        Mermaid code, if it exists on disk.
        """
        mermaid_hash = self._hash_mermaid(mermaid_code)
        path = os.path.join(self.output_dir, f"realistic_{mermaid_hash}.png")
        return path if os.path.exists(path) else None
```

### 4.3 Input/Output Summary

| Aspect | Detail |
|---|---|
| Input | Mermaid.js code string from `SessionStateManager.get_architectural_state()` |
| Intermediate | Natural-language scene description via `MermaidSceneTranslator` |
| API Call | `client.models.generate_images()` with `imagen-4.0-generate-001` |
| Output | PNG image bytes (16:9 aspect ratio) |
| Storage | `output/visualizations/realistic_<hash>.png` + in-memory cache |

---

## 5. Veo 3 Integration

### 5.1 Model and SDK

- **Model**: `veo-3.0-generate-preview` (latest Veo model on Vertex AI)
- **SDK**: `google-genai`
- **Location**: `us-central1`

### 5.2 Veo3DiagramAnimator Implementation

```python
# src/output/veo3_diagram_animator.py

import hashlib
import logging
import os
import time
from typing import Optional, Tuple

from google import genai
from google.genai import types

from src.state.session_state_manager import SessionStateManager

logger = logging.getLogger("fuse.veo3")


class Veo3DiagramAnimator:
    """
    Animates a photorealistic architecture image into a short walkthrough
    video using Google Veo 3 via Vertex AI.
    """

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
        """
        Constructs an animation prompt describing camera movement and
        data-flow visualization for the architecture scene.
        """
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

        # If we have mermaid code, add context-specific animation cues
        if mermaid_code:
            if "database" in mermaid_code.lower() or "db" in mermaid_code.lower():
                base_prompt += (
                    " Database cylinders emit a soft glow as queries arrive. "
                    "Read/write indicators pulse on the storage surfaces."
                )
            if "load" in mermaid_code.lower() and "balancer" in mermaid_code.lower():
                base_prompt += (
                    " The load balancer distributes glowing request orbs "
                    "across the downstream servers in a fan-out pattern."
                )
            if "queue" in mermaid_code.lower() or "kafka" in mermaid_code.lower():
                base_prompt += (
                    " Message queue pipelines show a conveyor-belt-like flow "
                    "of data packets moving steadily between producers and consumers."
                )
            if "cache" in mermaid_code.lower() or "redis" in mermaid_code.lower():
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
        """
        Generate an animated video from a photorealistic architecture image.

        Args:
            image_bytes: PNG image bytes from ImagenDiagramVisualizer.
            mermaid_code: Original Mermaid code for context-aware animation cues.
            duration_seconds: Target video duration (4-8 seconds).

        Returns:
            MP4 video bytes or None on failure.
        """
        if not image_bytes:
            logger.warning("No image bytes provided for animation.")
            return None

        image_hash = self._hash_image(image_bytes)

        # Check cache
        cached = self._get_cached(image_hash)
        if cached is not None:
            return cached

        animation_prompt = self.build_animation_prompt(mermaid_code)
        logger.info(
            "Animation prompt (%d chars): %s...",
            len(animation_prompt),
            animation_prompt[:120],
        )

        try:
            # Veo 3 image-to-video generation
            # The API accepts a reference image and a text prompt describing
            # the desired motion/animation.
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

            # Veo generation is asynchronous; poll until complete
            logger.info("Veo3 generation started. Polling for completion...")
            while not operation.done:
                time.sleep(5)
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
```

### 5.3 Input/Output Summary

| Aspect | Detail |
|---|---|
| Input | PNG image bytes from Imagen + optional Mermaid code for context |
| Animation Prompt | Camera movement + data-flow effects + component-specific cues |
| API Call | `client.models.generate_videos()` with `veo-3.0-generate-preview` |
| Polling | `client.operations.get(operation)` every 5 seconds until `operation.done` |
| Output | MP4 video bytes (16:9, 4-8 seconds, 24fps) |
| Storage | `output/animations/animation_<hash>.mp4` + in-memory cache |

---

## 6. New API Endpoints

All three endpoints are added to `main.py` alongside the existing `/render` endpoint.

### 6.1 GET /render/realistic

Generates (or returns cached) photorealistic image from the current Mermaid state.

```python
from fastapi.responses import Response

@app.get("/render/realistic")
async def render_realistic():
    """Generate a photorealistic image of the current architecture."""
    if not state_manager or not imagen_visualizer:
        return {"status": "error", "message": "System components not initialized."}

    mermaid_code = state_manager.get_architectural_state()
    if not mermaid_code:
        return {"status": "error", "message": "No architectural state to visualize."}

    image_bytes = await imagen_visualizer.generate(mermaid_code)
    if image_bytes:
        return Response(content=image_bytes, media_type="image/png")

    return {"status": "error", "message": "Failed to generate realistic visualization."}
```

### 6.2 GET /render/animate

Generates an animated video from the most recent realistic image.

```python
@app.get("/render/animate")
async def render_animate():
    """Generate an animated walkthrough video from the realistic image."""
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
```

### 6.3 GET /render/visualize

Full pipeline: Mermaid code to realistic image to animation, returning both assets.

```python
import base64

@app.get("/render/visualize")
async def render_visualize():
    """
    Full visualization pipeline: Mermaid -> photorealistic image -> animated video.
    Returns JSON with base64-encoded image and video.
    """
    if not state_manager or not imagen_visualizer or not veo3_animator:
        return {"status": "error", "message": "System components not initialized."}

    mermaid_code = state_manager.get_architectural_state()
    if not mermaid_code:
        return {"status": "error", "message": "No architectural state to visualize."}

    result = {"status": "success", "image": None, "video": None}

    # Step 1: Generate photorealistic image
    image_bytes = await imagen_visualizer.generate(mermaid_code)
    if image_bytes:
        result["image"] = base64.b64encode(image_bytes).decode("utf-8")
        result["image_mime"] = "image/png"
    else:
        return {"status": "error", "message": "Image generation failed."}

    # Step 2: Generate animation from the image
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
```

---

## 7. Web UI Changes

### 7.1 New Buttons

Add "Visualize" and "Animate" buttons to the diagram panel header in `static/index.html`:

```html
<!-- Inside #diagramPanel .panel-header .btn-group -->
<button class="btn btn-sm" onclick="fetchRenderedDiagram()">Render PNG</button>
<button class="btn btn-sm btn-blue" id="btnVisualize" onclick="generateRealistic()">Visualize</button>
<button class="btn btn-sm btn-blue" id="btnAnimate" onclick="generateAnimation()">Animate</button>
<button class="btn btn-sm" onclick="refreshMermaid()">Refresh</button>
```

### 7.2 Media Display Area

Add a media container below the Mermaid output area for showing realistic images and videos:

```html
<!-- Inside #diagramPanel .panel-body, after #mermaidOutput -->
<div id="realisticOutput" style="display:none; margin-top:8px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <span style="font-size:12px; color:#8b949e; font-weight:500;">REALISTIC VIEW</span>
        <button class="btn btn-sm" onclick="toggleDiagramView()">Show Diagram</button>
    </div>
    <img id="realisticImage" style="max-width:100%; border-radius:8px; display:none;" />
    <video id="realisticVideo" controls style="max-width:100%; border-radius:8px; display:none;"></video>
    <div id="genProgress" style="display:none; text-align:center; padding:32px; color:#8b949e;">
        <div class="spinner"></div>
        <span id="genProgressText">Generating...</span>
    </div>
</div>
```

### 7.3 Loading State CSS

```css
.spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #30363d;
    border-top: 3px solid #58a6ff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin: 0 auto 12px auto;
}
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
```

### 7.4 JavaScript Functions

```javascript
let currentView = 'diagram'; // 'diagram' | 'realistic'

function toggleDiagramView() {
    if (currentView === 'diagram') {
        document.getElementById('mermaidOutput').style.display = 'none';
        document.getElementById('realisticOutput').style.display = 'block';
        currentView = 'realistic';
    } else {
        document.getElementById('mermaidOutput').style.display = 'flex';
        document.getElementById('realisticOutput').style.display = 'none';
        currentView = 'diagram';
    }
}

function showGenProgress(text) {
    const el = document.getElementById('genProgress');
    document.getElementById('genProgressText').textContent = text;
    el.style.display = 'block';
    document.getElementById('realisticImage').style.display = 'none';
    document.getElementById('realisticVideo').style.display = 'none';
    // Switch to realistic view
    document.getElementById('mermaidOutput').style.display = 'none';
    document.getElementById('realisticOutput').style.display = 'block';
    currentView = 'realistic';
}

function hideGenProgress() {
    document.getElementById('genProgress').style.display = 'none';
}

async function generateRealistic() {
    showGenProgress('Generating photorealistic image with Imagen (10-30s)...');
    addMsg('system', 'Generating photorealistic visualization...');

    try {
        const resp = await fetch(BASE + '/render/realistic');
        if (resp.headers.get('content-type')?.includes('image/png')) {
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const img = document.getElementById('realisticImage');
            img.src = url;
            img.style.display = 'block';
            hideGenProgress();
            addMsg('system', 'Realistic visualization generated.');
        } else {
            const data = await resp.json();
            hideGenProgress();
            addMsg('system', 'Visualization error: ' + (data.message || 'Unknown error.'));
        }
    } catch (e) {
        hideGenProgress();
        addMsg('system', 'Visualization failed: ' + e.message);
    }
}

async function generateAnimation() {
    showGenProgress('Generating animated walkthrough with Veo 3 (30-120s)...');
    addMsg('system', 'Generating animated walkthrough...');

    try {
        const resp = await fetch(BASE + '/render/animate');
        if (resp.headers.get('content-type')?.includes('video/mp4')) {
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const video = document.getElementById('realisticVideo');
            video.src = url;
            video.style.display = 'block';
            document.getElementById('realisticImage').style.display = 'none';
            hideGenProgress();
            addMsg('system', 'Animated walkthrough generated.');
        } else {
            const data = await resp.json();
            hideGenProgress();
            addMsg('system', 'Animation error: ' + (data.message || 'Unknown error.'));
        }
    } catch (e) {
        hideGenProgress();
        addMsg('system', 'Animation failed: ' + e.message);
    }
}
```

---

## 8. Prompt Engineering Details

### 8.1 MermaidSceneTranslator

This module parses Mermaid.js syntax with regex (Mermaid code is structured enough for reliable extraction) and converts each node and edge into a visual scene description.

```python
# src/output/mermaid_scene_translator.py

import re
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("fuse.translator")


# --- Node Type to Visual Metaphor Mapping ---

NODE_VISUAL_MAP: Dict[str, str] = {
    # Infrastructure
    "server":        "a sleek rack-mounted server with blue LED status lights",
    "database":      "a cylindrical database storage unit with glowing data rings",
    "db":            "a cylindrical database storage unit with glowing data rings",
    "cache":         "a translucent high-speed memory module radiating warm light",
    "redis":         "a translucent high-speed memory module with a red-orange glow",
    "queue":         "a conveyor-belt pipeline with glowing data packets in transit",
    "kafka":         "a high-throughput streaming pipeline with parallel data lanes",
    "load_balancer": "a traffic control tower distributing beams of light to servers below",
    "lb":            "a traffic control tower distributing beams of light to servers below",
    "api":           "a gateway portal with a shimmering data membrane",
    "gateway":       "a fortified gateway arch with scanning beams",
    "cdn":           "a network of satellite relay nodes orbiting a central hub",
    "dns":           "a directory beacon tower broadcasting address signals",
    "firewall":      "a translucent energy shield wall with filtering patterns",
    "proxy":         "an intermediary relay station with routing indicators",
    "storage":       "a massive data vault with layered storage drawers",
    "s3":            "a cloud storage array floating with holographic access points",
    "blob":          "a cloud storage array floating with holographic access points",

    # Compute
    "gpu":           "a high-performance computing blade with heat-sink fins glowing orange",
    "cpu":           "a processing core with circuit-trace patterns pulsing with data",
    "container":     "a modular shipping-container-like compute pod",
    "docker":        "a modular blue compute container with the whale insignia",
    "kubernetes":    "an orchestration control deck managing rows of container pods",
    "k8s":           "an orchestration control deck managing rows of container pods",
    "lambda":        "a serverless execution orb that materializes on demand",
    "function":      "a serverless execution orb that materializes on demand",
    "vm":            "a virtual machine enclosure with a semitransparent shell",
    "worker":        "an industrial processing unit with conveyor input/output",

    # Application
    "frontend":      "a glass-panel user interface screen floating in space",
    "ui":            "a glass-panel user interface screen floating in space",
    "client":        "a user workstation with a holographic display",
    "browser":       "a browser window frame hovering above a user desk",
    "mobile":        "a smartphone device with an active touch interface",
    "backend":       "a server rack cluster behind a secure partition",
    "microservice":  "a small self-contained service pod with an API connector port",
    "service":       "a modular service unit with input/output connection ports",
    "auth":          "a biometric security checkpoint with scanning beams",
    "ml":            "a neural network processor with layered glowing nodes",
    "ai":            "an AI inference engine with radiating neural pathways",
    "model":         "a neural network processor with layered glowing nodes",
    "analytics":     "a data observatory dome with live dashboard projections",
    "monitoring":    "a surveillance command center with wall-mounted metric displays",
    "logging":       "a scrolling data recorder with continuous tape output",

    # External
    "user":          "a holographic user silhouette interacting with the system",
    "external":      "a distant system represented as a floating remote node",
    "third_party":   "a partner system module docked at the system boundary",
    "internet":      "a vast interconnected web of light filaments representing the global network",
}

# --- Relationship Type to Visual Connection Mapping ---

EDGE_VISUAL_MAP: Dict[str, str] = {
    "-->":   "connected by a glowing fiber-optic data stream flowing",
    "---":   "linked by a steady structural beam",
    "-.->":  "connected by a pulsing dashed energy trail flowing",
    "==>":   "joined by a thick high-bandwidth conduit carrying heavy data",
    "--o":   "attached via a monitoring probe",
    "--x":   "blocked by a terminated connection barrier",
    "o--o":  "sharing a bidirectional sync link",
}


class MermaidSceneTranslator:
    """
    Converts Mermaid.js diagram code into a natural-language scene
    description suitable for photorealistic image generation prompts.
    """

    def __init__(self, node_map: Dict[str, str] = None, edge_map: Dict[str, str] = None):
        self.node_map = node_map or NODE_VISUAL_MAP
        self.edge_map = edge_map or EDGE_VISUAL_MAP

    def _extract_nodes(self, mermaid_code: str) -> Dict[str, str]:
        """
        Extract node IDs and their labels from Mermaid code.
        Returns dict of {node_id: label}.
        """
        nodes: Dict[str, str] = {}

        # Match patterns like: NodeId[Label], NodeId(Label), NodeId{Label}, NodeId((Label))
        patterns = [
            r'(\w+)\[([^\]]+)\]',       # square brackets
            r'(\w+)\(([^)]+)\)',         # parentheses (round)
            r'(\w+)\{([^}]+)\}',         # curly braces (diamond/rhombus)
            r'(\w+)\(\(([^)]+)\)\)',      # double parens (circle)
            r'(\w+)\[\[([^\]]+)\]\]',    # double brackets (subroutine)
            r'(\w+)\[/([^\]]+)/\]',      # trapezoid
            r'(\w+)>\s*([^\]]+)\]',      # asymmetric
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, mermaid_code):
                node_id = match.group(1).strip()
                label = match.group(2).strip()
                if node_id not in ("graph", "flowchart", "subgraph", "end", "style", "classDef"):
                    nodes[node_id] = label

        # Also catch bare node IDs used in edges but not defined with labels
        edge_nodes = re.findall(r'(\w+)\s*(?:-->|---|-\.->|==>|--o|--x|o--o)', mermaid_code)
        edge_nodes += re.findall(r'(?:-->|---|-\.->|==>|--o|--x|o--o)\s*(\w+)', mermaid_code)
        for nid in edge_nodes:
            nid = nid.strip()
            if nid not in nodes and nid not in ("graph", "flowchart", "subgraph", "end", "style", "classDef"):
                nodes[nid] = nid

        return nodes

    def _extract_edges(self, mermaid_code: str) -> List[Tuple[str, str, str, str]]:
        """
        Extract edges from Mermaid code.
        Returns list of (source, edge_type, target, label).
        """
        edges: List[Tuple[str, str, str, str]] = []

        # Match: Source -->|label| Target or Source --> Target
        pattern = r'(\w+)\s*(-->|---|-\.->|==>|--o|--x|o--o)\s*(?:\|([^|]*)\|\s*)?(\w+)'
        for match in re.finditer(pattern, mermaid_code):
            source = match.group(1).strip()
            edge_type = match.group(2).strip()
            label = (match.group(3) or "").strip()
            target = match.group(4).strip()
            edges.append((source, edge_type, target, label))

        return edges

    def _extract_subgraphs(self, mermaid_code: str) -> List[Tuple[str, List[str]]]:
        """
        Extract subgraph groupings.
        Returns list of (subgraph_label, [node_ids]).
        """
        subgraphs: List[Tuple[str, List[str]]] = []

        # Match subgraph blocks
        sg_pattern = r'subgraph\s+(.+?)(?:\n|\r)(.*?)end'
        for match in re.finditer(sg_pattern, mermaid_code, re.DOTALL):
            label = match.group(1).strip().strip('"').strip("'")
            body = match.group(2)
            # Find node IDs inside the subgraph body
            body_nodes = re.findall(r'(\w+)(?:\[|\(|\{|-->|---)', body)
            subgraphs.append((label, body_nodes))

        return subgraphs

    def _match_visual(self, label: str) -> str:
        """
        Match a node label to the best visual metaphor from the mapping.
        Falls back to a generic description.
        """
        label_lower = label.lower().replace(" ", "_").replace("-", "_")

        # Direct match
        if label_lower in self.node_map:
            return self.node_map[label_lower]

        # Partial match: check if any key appears in the label
        for key, visual in self.node_map.items():
            if key in label_lower:
                return visual

        # Generic fallback
        return f"a technical component labeled '{label}' with indicator lights and data ports"

    def translate(self, mermaid_code: str) -> str:
        """
        Translate full Mermaid.js code into a scene description string.
        """
        nodes = self._extract_nodes(mermaid_code)
        edges = self._extract_edges(mermaid_code)
        subgraphs = self._extract_subgraphs(mermaid_code)

        scene_parts: List[str] = []

        # Describe the overall scene
        node_count = len(nodes)
        scene_parts.append(
            f"A sprawling modern technology infrastructure with {node_count} "
            f"distinct components arranged in an organized layout."
        )

        # Describe subgraphs as zones
        for sg_label, sg_nodes in subgraphs:
            zone_desc = (
                f"A clearly delineated zone labeled '{sg_label}' "
                f"containing {len(sg_nodes)} components, "
                f"enclosed by a subtle boundary glow."
            )
            scene_parts.append(zone_desc)

        # Describe nodes
        for node_id, label in nodes.items():
            visual = self._match_visual(label)
            scene_parts.append(f"Component '{label}' represented as {visual}.")

        # Describe edges/connections
        for source, edge_type, target, label in edges:
            source_label = nodes.get(source, source)
            target_label = nodes.get(target, target)
            edge_visual = self.edge_map.get(edge_type, "connected by a data link")

            edge_desc = f"'{source_label}' is {edge_visual} to '{target_label}'"
            if label:
                edge_desc += f" carrying '{label}' data"
            edge_desc += "."
            scene_parts.append(edge_desc)

        return " ".join(scene_parts)
```

### 8.2 Node Type to Visual Metaphor Mapping (reference table)

| Node Keyword | Visual Metaphor |
|---|---|
| server | Sleek rack-mounted server with blue LED status lights |
| database / db | Cylindrical storage unit with glowing data rings |
| cache / redis | Translucent high-speed memory module radiating warm light |
| load_balancer / lb | Traffic control tower distributing beams of light |
| api / gateway | Gateway portal with shimmering data membrane |
| firewall | Translucent energy shield wall with filtering patterns |
| gpu | High-performance computing blade with heat-sink fins glowing orange |
| container / docker | Modular shipping-container compute pod |
| kubernetes / k8s | Orchestration control deck managing container pods |
| frontend / ui / client | Glass-panel interface screen floating in space |
| queue / kafka | Conveyor-belt pipeline with glowing data packets |
| ml / ai / model | Neural network processor with layered glowing nodes |
| user | Holographic user silhouette |

### 8.3 Relationship Type to Visual Connection Mapping

| Mermaid Edge | Visual Representation |
|---|---|
| `-->` | Glowing fiber-optic data stream |
| `---` | Steady structural beam |
| `-.->` | Pulsing dashed energy trail |
| `==>` | Thick high-bandwidth conduit |
| `--o` | Monitoring probe attachment |
| `--x` | Terminated connection barrier |

### 8.4 Example Prompts

**Input Mermaid:**
```
graph TD
    LB[Load Balancer] --> API1[API Server 1]
    LB --> API2[API Server 2]
    API1 --> DB[(PostgreSQL)]
    API2 --> DB
    API1 --> Cache[Redis Cache]
    API2 --> Cache
```

**Generated Scene Description (from MermaidSceneTranslator):**
> A sprawling modern technology infrastructure with 5 distinct components arranged in an organized layout. Component 'Load Balancer' represented as a traffic control tower distributing beams of light to servers below. Component 'API Server 1' represented as a gateway portal with a shimmering data membrane. Component 'API Server 2' represented as a gateway portal with a shimmering data membrane. Component 'PostgreSQL' represented as a cylindrical database storage unit with glowing data rings. Component 'Redis Cache' represented as a translucent high-speed memory module with a red-orange glow. 'Load Balancer' is connected by a glowing fiber-optic data stream flowing to 'API Server 1'. 'Load Balancer' is connected by a glowing fiber-optic data stream flowing to 'API Server 2'. 'API Server 1' is connected by a glowing fiber-optic data stream flowing to 'PostgreSQL'. 'API Server 2' is connected by a glowing fiber-optic data stream flowing to 'PostgreSQL'. 'API Server 1' is connected by a glowing fiber-optic data stream flowing to 'Redis Cache'. 'API Server 2' is connected by a glowing fiber-optic data stream flowing to 'Redis Cache'.

**Full Imagen Prompt (prepended by ImagenDiagramVisualizer):**
> Create a photorealistic, highly detailed architectural visualization. The scene depicts a modern technology infrastructure viewed from a slightly elevated isometric perspective with dramatic lighting. [scene description above] Style: photorealistic CGI render, cinematic lighting, depth of field, 8K detail, technical precision. No text labels or annotations.

---

## 9. State Management

### 9.1 Caching Strategy

| Layer | Mechanism | TTL | Key |
|---|---|---|---|
| Imagen in-memory | `dict[mermaid_hash -> (bytes, timestamp)]` | 5 min | SHA-256 of Mermaid code (first 16 hex chars) |
| Veo 3 in-memory | `dict[image_hash -> (bytes, timestamp)]` | 10 min | SHA-256 of image bytes (first 16 hex chars) |
| Disk persistence | `output/visualizations/` and `output/animations/` | Until cleanup | `realistic_<hash>.png`, `animation_<hash>.mp4` |

### 9.2 Redis Event Logging

Both components log generation events to Redis via `SessionStateManager.log_event()`:

- Event type `imagen_generation`: records `mermaid_hash`, `image_size`, `output_path`
- Event type `veo3_animation`: records `image_hash`, `video_size`, `duration`, `output_path`

### 9.3 Future: Cloud Storage

For production deployments where Cloud Run instances are ephemeral and `output/` does not persist across deployments, migrate file storage to Google Cloud Storage:

```python
# Future enhancement: GCS-backed storage
from google.cloud import storage

BUCKET_NAME = "fuse-generated-media"

def upload_to_gcs(local_path: str, blob_name: str) -> str:
    client = storage.Client(project="fuse-489616")
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path)
    return f"gs://{BUCKET_NAME}/{blob_name}"
```

---

## 10. Error Handling and Fallbacks

### 10.1 Error Scenarios

| Scenario | Handling | Fallback |
|---|---|---|
| Imagen API returns no images | Log error, return `None` | Web UI shows standard Mermaid SVG diagram |
| Imagen API rate limit (429) | Log, return error JSON to client | Retry message shown in UI with "try again" suggestion |
| Imagen content policy block | Log the blocked prompt, return error | Display the Mermaid SVG; notify user the scene was filtered |
| Veo 3 operation timeout (> 3 min) | Cancel polling loop, return `None` | Show the static Imagen image instead of video |
| Veo 3 API not available | Catch exception, log, return error | Image-only mode; "Animate" button disabled with tooltip |
| Mermaid parsing failure | `MermaidSceneTranslator` returns minimal generic prompt | Imagen receives generic "technology infrastructure" prompt |
| Redis unavailable | Generation still works (no event logging) | Cache operates in-memory only |
| Disk write failure | Catch `IOError`, log, continue | In-memory cache still serves the result |

### 10.2 Timeout Configuration

```python
# Recommended timeout values
IMAGEN_TIMEOUT_SECONDS = 60      # Kill request after 60s
VEO3_POLL_TIMEOUT_SECONDS = 180  # Stop polling after 3 minutes
VEO3_POLL_INTERVAL_SECONDS = 5   # Poll every 5 seconds
```

### 10.3 Client-Side Error Display

The web UI JavaScript functions already handle non-image/video responses by parsing JSON error messages and displaying them through `addMsg('system', ...)`. The loading spinner is always hidden in both success and error paths via `hideGenProgress()`.

---

## 11. Implementation Checklist

| # | Task | File Path | Complexity | Depends On |
|---|---|---|---|---|
| 1 | Create `MermaidSceneTranslator` with node/edge parsing and visual mapping | `src/output/mermaid_scene_translator.py` | Medium | -- |
| 2 | Create `ImagenDiagramVisualizer` with caching and disk persistence | `src/output/imagen_diagram_visualizer.py` | Medium | #1 |
| 3 | Create `Veo3DiagramAnimator` with polling and caching | `src/output/veo3_diagram_animator.py` | Medium | -- |
| 4 | Add `GET /render/realistic` endpoint to `main.py` | `main.py` | Low | #2 |
| 5 | Add `GET /render/animate` endpoint to `main.py` | `main.py` | Low | #2, #3 |
| 6 | Add `GET /render/visualize` endpoint to `main.py` | `main.py` | Low | #2, #3 |
| 7 | Initialize `ImagenDiagramVisualizer` and `Veo3DiagramAnimator` in `start_agents()` | `main.py` | Low | #2, #3 |
| 8 | Add import statements for new modules in `main.py` | `main.py` | Low | #2, #3 |
| 9 | Add "Visualize" and "Animate" buttons to diagram panel header | `static/index.html` | Low | -- |
| 10 | Add `#realisticOutput` media display area with image/video elements | `static/index.html` | Low | -- |
| 11 | Add spinner CSS and generation progress styling | `static/index.html` | Low | -- |
| 12 | Add `generateRealistic()`, `generateAnimation()`, and view-toggle JS | `static/index.html` | Medium | #4, #5 |
| 13 | Add `google-cloud-storage` to `requirements.txt` (future GCS support) | `requirements.txt` | Low | -- |
| 14 | Create output directories in `Dockerfile` | `Dockerfile` | Low | -- |
| 15 | Write unit tests for `MermaidSceneTranslator` | `tests/test_mermaid_scene_translator.py` | Medium | #1 |
| 16 | Write integration tests for Imagen and Veo 3 (mocked) | `tests/test_visualization_pipeline.py` | Medium | #2, #3 |

### Estimated Total Effort

- **New Python files**: 3 (`mermaid_scene_translator.py`, `imagen_diagram_visualizer.py`, `veo3_diagram_animator.py`)
- **Modified files**: 3 (`main.py`, `static/index.html`, `requirements.txt`)
- **Optional/future files**: 1 (`Dockerfile`)
- **Test files**: 2
- **Estimated LOC**: ~700 new lines across all files
- **Estimated time**: 2-3 days for a developer familiar with the codebase

---

## 12. Dependencies

### 12.1 Existing (already in requirements.txt)

| Package | Usage |
|---|---|
| `google-genai` | SDK for Imagen and Veo 3 APIs via Vertex AI |
| `google-cloud-aiplatform` | Vertex AI platform support |
| `fastapi` | HTTP endpoints |
| `redis` | Session state and event logging |

### 12.2 New (add to requirements.txt)

| Package | Usage | Required? |
|---|---|---|
| `google-cloud-storage` | Future: persist generated media to GCS | Optional (for production) |

No new pip packages are strictly required. The `google-genai` SDK already includes support for both `generate_images` (Imagen) and `generate_videos` (Veo 3) via the unified `client.models` interface.

### 12.3 API Enablement

Ensure the following APIs are enabled in GCP project `fuse-489616`:

- `aiplatform.googleapis.com` (already enabled)
- Imagen and Veo access may require allowlist approval or quota grants depending on the Vertex AI tier

### 12.4 Dockerfile Changes

Add output directories for generated media:

```dockerfile
# After existing COPY/RUN commands
RUN mkdir -p output/visualizations output/animations
```

---

## Appendix: Quick Reference for API Calls

### Imagen (generate_images)

```python
response = client.models.generate_images(
    model="imagen-4.0-generate-001",
    prompt="...",
    config=types.GenerateImagesConfig(
        number_of_images=1,
        aspect_ratio="16:9",
        output_mime_type="image/png",
    ),
)
image_bytes = response.generated_images[0].image.image_bytes
```

### Veo 3 (generate_videos)

```python
operation = client.models.generate_videos(
    model="veo-3.0-generate-preview",
    prompt="...",
    image=types.Image(image_bytes=img_bytes, mime_type="image/png"),
    config=types.GenerateVideosConfig(
        aspect_ratio="16:9",
        number_of_videos=1,
        duration_seconds=6,
        person_generation="dont_allow",
    ),
)
# Poll
while not operation.done:
    time.sleep(5)
    operation = client.operations.get(operation)

video_bytes = operation.response.generated_videos[0].video.video_bytes
```
