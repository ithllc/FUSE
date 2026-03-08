# FUSE: Errors & Issues Found from Previous Implementation

**Date**: 2026-03-08
**Reviewed by**: Claude Code (Code Review Agent)

---

## Summary

The previous coding agent built the overall structure and architecture correctly but made **critical errors** in model names, deployment configuration, Docker build, test compatibility, and GCP infrastructure connectivity. **No Cloud Run service was ever successfully deployed** — all 4 Cloud Build attempts failed.

---

## GCP Service Status

| Service | Status | Notes |
|:---|:---|:---|
| **Cloud Run** | **NOT DEPLOYED** | 0 services exist. All Cloud Builds failed. |
| **Cloud Memorystore Redis** | **EXISTS** | `fuse-session-store` at `10.8.239.3:6379` (BASIC tier, 1GB, us-central1) |
| **Cloud Build** | **4 FAILED builds** | Docker build fails on obsolete package `libgl1-mesa-glx` |
| **Artifact Registry** | **NO repos exist** | `cloudbuild.yaml` uses deprecated `gcr.io` Container Registry |
| **Serverless VPC Access** | **API NOT ENABLED** | Cloud Run cannot reach Memorystore Redis without a VPC connector |
| **Vertex AI API** | Enabled | ✓ |
| **Cloud Run API** | Enabled | ✓ |
| **Memorystore Redis API** | Enabled | ✓ |

---

## Error #1: Gemini Model Names Are Wrong

**Severity**: CRITICAL — Application cannot function
**Files affected**: `src/audio/gemini_live_stream_handler.py`, `src/agents/proof_orchestrator.py`

| Used in Code | Correct Model ID | Component |
|:---|:---|:---|
| `gemini-3.1-flash-live` | `gemini-2.5-flash-native-audio-preview-12-2025` | GeminiLiveStreamHandler (Live API) |
| `gemini-3.1-pro` | `gemini-3.1-pro-preview` | ProofOrchestrator |
| `gemini-3.1-flash-lite-preview` | `gemini-3.1-flash-lite-preview` ✓ | VisionStateCapture (correct) |

**Details**: There is no Gemini 3 series model that supports the Live API. The Live API (real-time bidirectional audio/video streaming) is only supported by `gemini-2.5-flash-native-audio-preview-12-2025`. The PRD referenced "Gemini 3.1 Flash Live" but this model does not exist. The ProofOrchestrator used `gemini-3.1-pro` which is missing the `-preview` suffix.

---

## Error #2: Dockerfile Build Failure (Blocks All Deployment)

**Severity**: CRITICAL — Prevents Cloud Build and Cloud Run deployment
**File affected**: `Dockerfile`

**Root cause**: `libgl1-mesa-glx` package was removed/renamed in Debian Trixie (used by `python:3.11-slim`). The Dockerfile also installs unnecessary OpenGL libraries since `opencv-python-headless` is used (which doesn't need OpenGL).

**Cloud Build error**:
```
E: Package 'libgl1-mesa-glx' has no installation candidate
```

**Additional issues in Dockerfile**:
- Missing `libasound2t64` (Debian Trixie renamed `libasound2`)
- Missing Puppeteer configuration for Mermaid CLI in container environments
- Should use `opencv-python-headless` system deps only (no GL needed)

---

## Error #3: No VPC Connector for Cloud Run → Redis

**Severity**: CRITICAL — Cloud Run cannot reach Memorystore Redis
**Infrastructure gap**: Serverless VPC Access API not even enabled

**Details**: Google Cloud Memorystore Redis (`10.8.239.3`) is only accessible via private VPC networking. Cloud Run requires a Serverless VPC Access connector to reach it. Without this, even if the Docker build succeeded, the app would fail at runtime with Redis connection errors.

**Required**:
1. Enable `vpcaccess.googleapis.com` API
2. Create a VPC connector in `us-central1`
3. Configure Cloud Run service with `--vpc-connector` flag

---

## Error #4: Deprecated Container Registry (`gcr.io`)

**Severity**: MODERATE
**Files affected**: `cloudbuild.yaml`

Google Container Registry (`gcr.io`) is deprecated in favor of Artifact Registry. The `cloudbuild.yaml` pushes to `gcr.io/${PROJECT_ID}/fuse-service` but no Artifact Registry repository exists. Should migrate to `us-central1-docker.pkg.dev/${PROJECT_ID}/fuse-repo/fuse-service`.

---

## Error #5: Tests Reference Non-Existent Methods

**Severity**: MODERATE — Tests will fail
**File affected**: `tests/test_vision_state.py`

The test file calls:
- `vision_capture._analyze_frame(dummy_frame)` — method does not exist
- `vision_capture.capture_and_analyze(fps=100)` — method does not exist

The `VisionStateCapture` class was refactored to use `process_received_frame(bytes)` (HTTP endpoint pattern) but the tests were never updated to match.

---

## Error #6: ProofOrchestrator Never Runs Periodically

**Severity**: MODERATE — Architecture validation never executes
**File affected**: `main.py`

The `ProofOrchestrator` is initialized in `start_agents()` but is never scheduled to run. The PRD and architecture docs state it should "periodically fetch the latest Mermaid code from Redis" for validation. The `po` variable is created but never used after initialization.

---

## Error #7: Missing `__init__.py` Files in `src/` Packages

**Severity**: LOW-MODERATE — May cause import issues
**Directories affected**: `src/`, `src/audio/`, `src/vision/`, `src/state/`, `src/agents/`, `src/output/`

No `__init__.py` files exist in any `src/` subdirectory. While Python 3 supports implicit namespace packages, explicit `__init__.py` files are best practice and required for some tooling.

---

## Error #8: `.gitignore` Header References Wrong Project

**Severity**: LOW
**File affected**: `.gitignore`

The `.gitignore` file has the comment `# OpenTaxCopilot Git Ignore` — this should reference FUSE.

---

## Error #9: Location Configuration

**Severity**: LOW
**Files affected**: `main.py`, `.env`, all model initializations

Per Google Senior Engineer guidance, when region is `us-central1`, the Vertex AI location can be set to `global` for broader model availability (especially for preview models). Current code hardcodes `us-central1`.

---

## Error #10: `server.log` Tracked in Repository

**Severity**: LOW
**File affected**: `server.log`

A `server.log` file exists in the repo root but `*.log` is in `.gitignore`. This file should be removed from tracking.

---

## Resolution Status

All 10 errors have been fixed:

| Error | Fix Applied |
|:---|:---|
| #1 Model Names | Corrected to `gemini-2.5-flash-native-audio-preview-12-2025`, `gemini-3.1-pro-preview`, and `gemini-3.1-flash-lite-preview` |
| #2 Dockerfile | Replaced `libgl1-mesa-glx` with correct deps, added Chromium + Puppeteer config for Mermaid CLI |
| #3 VPC Connector | Enabled VPC Access API, created `fuse-vpc-connector`, added `--vpc-connector` to `cloudbuild.yaml` |
| #4 Container Registry | Migrated to Artifact Registry (`us-central1-docker.pkg.dev/fuse-489616/fuse-repo/`) |
| #5 Tests | Rewrote `test_vision_state.py` to test `process_received_frame()` with byte input |
| #6 ProofOrchestrator | Added periodic validation loop (60s) in `main.py` + `/validate` endpoint |
| #7 `__init__.py` | Created `__init__.py` in all `src/` subdirectories |
| #8 `.gitignore` | Fixed header to reference FUSE |
| #9 Location | Changed default location to `global` in all components and `.env` |
| #10 `server.log` | Removed from git tracking |

**Cloud Run Service**: Successfully deployed at `https://fuse-service-864533297567.us-central1.run.app`

---

## What Was Done Correctly

- Overall FastAPI application structure and endpoint design
- WebSocket `/live` endpoint pattern for bidirectional streaming
- HTTP POST `/vision/frame` endpoint for frame ingestion
- `SessionStateManager` Redis schema and operations
- `DiagramRenderer` Mermaid CLI integration
- `client_streamer.py` multimodal client with camera/mic capture
- Architecture documentation (Mermaid diagrams, workflow docs)
- Cloud Build trigger and GitHub Actions workflow structure
- `.env` configuration pattern
- `VisionStateCapture.process_received_frame()` implementation using google-genai SDK correctly
