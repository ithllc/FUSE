# Technical Implementation Plan: Gemini Live API Audio+Video Streaming

**Source PRD**: `docs/coding_implementations/LIVE_API_VIDEO_STREAMING_PRD.md`
**Target Issue**: #22
**Estimated Effort**: ~4 hours (3 files, 1 new coroutine, client-side frame routing)

---

## Overview

Add real-time video streaming to the Gemini Live API session so Gemini can **see** what the user is showing (whiteboards, objects, gestures) alongside audio. Video frames are sent at 1 FPS via `session.send_realtime_input(video=Blob)` as a **separate call** from audio (the API accepts only one parameter per call). The existing REST `/vision/frame` pipeline continues running in parallel for detailed Mermaid extraction.

### Architecture Change

```
Before:
  Browser ──audio──► WebSocket /live ──audio──► Gemini Live API
  Browser ──frames──► POST /vision/frame ──► VisionStateCapture (Mermaid extraction)

After:
  Browser ──audio──► WebSocket /live ──audio──► Gemini Live API
  Browser ──frames──► WebSocket /live ──video──► Gemini Live API (awareness)
  Browser ──frames──► POST /vision/frame ──► VisionStateCapture (Mermaid extraction)
```

Both video-to-Live-API (awareness) and REST /vision/frame (extraction) receive the same frames. The client sends frames through **two parallel paths**.

---

## Phase 1: Server-Side Video Sender Coroutine

### Objective
Add a `video_sender` async task inside the `/live` WebSocket handler that reads buffered frames and sends them to the Gemini Live API at 1 FPS.

### Implementation Steps

#### 1.1 Add video frame buffer and tracking globals (`main.py`)

Add alongside existing `_latest_frame`:
```python
# Video streaming state for observability (issue #22)
_video_streaming = False
_video_frames_sent = 0
_video_last_error = None
```

#### 1.2 Add `video_sender` coroutine inside the reconnect loop (`main.py`)

Inside the `while client_connected and reconnect_count < MAX_RECONNECTS` block, alongside `receive_from_client`, `send_to_client`, and `keepalive_ping`:

```python
async def video_sender():
    """Send camera frames to Gemini Live API at 1 FPS for visual awareness (issue #22)."""
    nonlocal _video_streaming, _video_frames_sent, _video_last_error
    import io
    try:
        _video_streaming = True
        _video_frames_sent = 0
        _video_last_error = None

        # Notify client that video streaming started
        await websocket.send_text(json.dumps({
            "type": "video_status",
            "status": "streaming",
            "message": "VIDEO: Streaming at 1 FPS (768x768)"
        }))
        logger.info("VIDEO: Streaming started (1 FPS, 768x768)")

        while session_active and client_connected:
            await asyncio.sleep(1.0)  # 1 FPS

            if not session_active or not client_connected:
                break

            frame = _latest_frame
            if frame is None:
                continue

            try:
                # Resize to 768x768 and compress to JPEG quality 70
                resized = _resize_frame_for_live_api(frame)

                video_blob = genai_types.Blob(
                    data=resized,
                    mime_type="image/jpeg"
                )
                await session.send_realtime_input(video=video_blob)
                _video_frames_sent += 1

                # Log every 30 frames (30 seconds)
                if _video_frames_sent % 30 == 0:
                    logger.info(f"VIDEO: {_video_frames_sent} frames sent")
                    await websocket.send_text(json.dumps({
                        "type": "video_status",
                        "status": "streaming",
                        "frames_sent": _video_frames_sent
                    }))

            except Exception as e:
                _video_last_error = str(e)
                logger.warning(f"VIDEO: Frame send failed — {e}")
                # Don't break — keep trying on next frame

    except asyncio.CancelledError:
        pass
    finally:
        _video_streaming = False
        logger.info(f"VIDEO: Streaming stopped ({_video_frames_sent} frames sent)")
```

#### 1.3 Add frame resize helper function (`main.py`)

Add a module-level helper that resizes frames to 768x768 JPEG:

```python
def _resize_frame_for_live_api(frame_bytes: bytes) -> bytes:
    """Resize frame to 768x768 JPEG quality 70 for Gemini Live API video input."""
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(frame_bytes))
        img = img.resize((768, 768), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=70)
        return buf.getvalue()
    except ImportError:
        # Fallback: send raw frame if Pillow not available
        return frame_bytes
```

#### 1.4 Register video_sender as the 4th task (`main.py`)

Change the task list from 3 to 4:
```python
tasks = [
    asyncio.create_task(receive_from_client()),
    asyncio.create_task(send_to_client()),
    asyncio.create_task(keepalive_ping()),
    asyncio.create_task(video_sender()),
]
```

#### 1.5 Reset video state on reconnect

At the top of each reconnect iteration, reset:
```python
_video_streaming = False
_video_frames_sent = 0
```

### Files Modified
- `main.py`: Lines ~48-50 (new globals), ~258 (new coroutine), ~523 (task list), new helper function

### Dependencies
- `Pillow` (PIL) for frame resizing — already in `requirements.txt`
- `_latest_frame` global already populated by `POST /vision/frame` handler

---

## Phase 2: Client-Side Dual Frame Routing

### Objective
Send camera frames through **both** the WebSocket (for Live API video) **and** the REST endpoint (for Mermaid extraction) simultaneously.

### Implementation Steps

#### 2.1 Add WebSocket frame sender (`static/index.html`)

Add a new function alongside `sendVideoFrameHTTP()`:

```javascript
let videoFrameInterval = null;

function sendVideoFrameWS() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const video = document.getElementById('localVideo');
    const canvas = document.getElementById('captureCanvas');
    canvas.width = 768;
    canvas.height = 768;
    const ctx = canvas.getContext('2d');

    // Center-crop to square then draw at 768x768
    const vw = video.videoWidth, vh = video.videoHeight;
    const side = Math.min(vw, vh);
    const sx = (vw - side) / 2, sy = (vh - side) / 2;
    ctx.drawImage(video, sx, sy, side, side, 0, 0, 768, 768);

    canvas.toBlob((blob) => {
        if (!blob || !ws || ws.readyState !== WebSocket.OPEN) return;
        blob.arrayBuffer().then(buf => {
            // Send as binary with a 'V' prefix byte to distinguish from audio
            const prefix = new Uint8Array([0x56]); // 'V' = 0x56
            const frame = new Uint8Array(buf);
            const combined = new Uint8Array(prefix.length + frame.length);
            combined.set(prefix);
            combined.set(frame, prefix.length);
            ws.send(combined.buffer);
        });
    }, 'image/jpeg', 0.7);
}
```

#### 2.2 Start/stop WebSocket video streaming on session state change

In the session start flow (after diagnostics pass):
```javascript
// Start video streaming to Live API at 1 FPS
if (cameraStream) {
    videoFrameInterval = setInterval(() => {
        if (sessionState === 'active') sendVideoFrameWS();
    }, 1000);
    addConnectionLog('VIDEO: Streaming to Live API at 1 FPS', 'ok');
}
```

In session end/cleanup:
```javascript
if (videoFrameInterval) {
    clearInterval(videoFrameInterval);
    videoFrameInterval = null;
}
```

#### 2.3 Handle video_status messages from server

In the WebSocket message handler, add:
```javascript
if (data.type === 'video_status') {
    if (data.frames_sent) {
        addConnectionLog('VIDEO: ' + data.frames_sent + ' frames sent', 'ok');
    } else if (data.message) {
        addConnectionLog(data.message, 'ok');
    }
    return;
}
```

### Files Modified
- `static/index.html`: New `sendVideoFrameWS()` function, interval management, message handler

---

## Phase 3: Server-Side Frame Routing (Distinguish Audio vs Video)

### Objective
The WebSocket `/live` handler must distinguish binary audio frames from binary video frames sent by the client.

### Implementation Steps

#### 3.1 Update `receive_from_client()` to detect video frames (`main.py`)

Currently, all binary WebSocket messages are treated as audio. Change to check the prefix byte:

```python
async def receive_from_client():
    nonlocal session_active, client_connected
    try:
        while session_active:
            message = await websocket.receive()
            if "bytes" in message:
                raw = message["bytes"]
                # Check for video frame prefix 'V' (0x56) — issue #22
                if len(raw) > 1 and raw[0:1] == b'V':
                    # Video frame — update latest frame buffer
                    _latest_frame = raw[1:]
                else:
                    # Audio frame — send to Gemini Live API
                    audio_blob = genai_types.Blob(
                        data=raw,
                        mime_type="audio/pcm;rate=16000"
                    )
                    await session.send_realtime_input(audio=audio_blob)
            elif "text" in message:
                # ... existing text handling unchanged ...
```

This way:
- Audio bytes (raw PCM, no prefix) → sent directly to Gemini via `send_realtime_input(audio=)`
- Video bytes (prefixed with `V`) → stored in `_latest_frame` buffer, sent by `video_sender` coroutine via `send_realtime_input(video=)`

The `_latest_frame` buffer is the same one used by `POST /vision/frame` and by the `capture_and_analyze_frame` function call. Both the WebSocket video path and the REST path update it.

### Files Modified
- `main.py`: `receive_from_client()` function (~line 394)

---

## Phase 4: Observability

### Objective
Make video streaming state visible in connection log, health check, and Cloud Run structured logging.

### Implementation Steps

#### 4.1 Add video state to `/health` endpoint (`main.py`)

In the health check function, add a `video_streaming` component:

```python
# Video streaming state (issue #22)
components["video_streaming"] = {
    "status": "streaming" if _video_streaming else "idle",
    "frames_sent": _video_frames_sent,
    "fps": 1,
    "last_error": _video_last_error,
}
```

#### 4.2 Connection log entries (already in Phase 1 & 2)

The `video_sender` coroutine and client-side code already emit:
- `"VIDEO: Streaming at 1 FPS (768x768)"` — on start
- `"VIDEO: 30 frames sent"` — every 30 seconds
- `"VIDEO: Frame send failed — [reason]"` — on error
- `"VIDEO: Streaming stopped (N frames sent)"` — on end

#### 4.3 Cloud Run structured logging (already in Phase 1)

The `video_sender` coroutine uses `logger.info()` and `logger.warning()` which are captured by Cloud Run's structured logging via stderr.

#### 4.4 Update system instruction to mention video awareness

In `gemini_live_stream_handler.py`, update the system instruction to tell Gemini it can now see:

```python
"REAL-TIME VISION: You are receiving live camera frames at 1 FPS. You can see "
"what the user is showing you — whiteboards, physical objects, hand gestures, "
"and spatial arrangements. Use this visual context to understand deictic "
"references like 'this', 'that', 'over here'. When you see something relevant, "
"mention it proactively. You ALSO have the capture_and_analyze_frame function "
"for detailed analysis — use it when the user asks you to 'look closely' or "
"when you need the vision pipeline to extract a Mermaid diagram from what you see."
```

### Files Modified
- `main.py`: `/health` endpoint (~line 84)
- `src/audio/gemini_live_stream_handler.py`: system instruction (~line 142)

---

## Phase 5: Dependencies & Build

### Objective
Ensure Pillow is available and verify no breaking changes.

### Implementation Steps

#### 5.1 Verify Pillow in requirements.txt

`Pillow` should already be present (used by VisionStateCapture for OpenCV/image operations). Verify and add if missing.

#### 5.2 Verify OpenCV not required

The resize uses Pillow (PIL), not OpenCV, to avoid adding a heavy dependency. Pillow's `Image.resize()` with `LANCZOS` produces high-quality 768x768 output.

### Files Modified
- `requirements.txt` (verify only — Pillow should already be listed)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Token exhaustion from video+audio | Low | High | SlidingWindow compression (issue #18) already handles this |
| Frame send blocking audio | Low | Medium | Separate coroutine; `send_realtime_input` calls are independent |
| Prefix byte collision with audio | Very Low | Medium | PCM audio never starts with 0x56 at the rates we use; first audio byte is always part of a 16-bit sample |
| Pillow import failure in container | Very Low | Low | Fallback sends raw frame without resize |
| Gemini rejects video input | Low | High | Model `gemini-live-2.5-flash-native-audio` supports `send_realtime_input(video=)` per API docs |

---

## Success Criteria

1. **Video frames reach Gemini**: Connection log shows "VIDEO: 30 frames sent" every 30 seconds
2. **Audio continues working**: Mic check diagnostic still passes; Gemini responds with audio
3. **Session lasts 5 minutes**: SlidingWindow keeps context under 128K tokens
4. **Gemini describes what it sees**: Without function call, Gemini can say "I see you holding a stapler"
5. **Function calls still work**: `capture_and_analyze_frame` triggers REST pipeline for detailed Mermaid extraction
6. **Health check reports video**: `/health` includes `video_streaming` component
7. **REST pipeline unchanged**: `POST /vision/frame` at 0.5 FPS continues for two-pass Mermaid extraction

---

## File Manifest

| File | Changes |
|------|---------|
| `main.py` | Add `_resize_frame_for_live_api()`, video globals, `video_sender()` coroutine, update `receive_from_client()` for prefix routing, update `/health`, register 4th task |
| `static/index.html` | Add `sendVideoFrameWS()`, start/stop interval, handle `video_status` messages |
| `src/audio/gemini_live_stream_handler.py` | Update system instruction to mention real-time vision |
| `requirements.txt` | Verify Pillow present |

---

## Handoff

- Run `/project` to ingest this plan into the kanban board
- Create GitHub Issue #22 referencing this plan and the PRD
