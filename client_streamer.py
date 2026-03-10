import cv2
import asyncio
import websockets
import json
import base64
import time
import argparse
import threading
import queue
import numpy as np

# Requirements: pip install opencv-python websockets requests pyaudio
try:
    import pyaudio
except ImportError:
    print("Warning: pyaudio not found. Audio streaming will be disabled.")
    pyaudio = None

class FuseMultimodalClient:
    def __init__(self, url, fps=2):
        self.url = url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/") + "/live"
        self.fps = fps
        self.video_cap = cv2.VideoCapture(0)
        self.audio_queue = queue.Queue()
        self.is_running = True

        # Audio settings
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16 if pyaudio else None
        self.CHANNELS = 1
        self.RATE = 16000 # 16kHz is standard for Gemini Live

    def generate_test_frame(self):
        """Generates a synthetic frame for testing in environments without camera access."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Background color
        frame[:] = (50, 30, 30)
        # Add text
        text = f"FUSE LIVE TEST | {time.strftime('%H:%M:%S')}"
        cv2.putText(frame, text, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, "WSL2 Virtual Stream Active", (50, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 1)
        return frame

    def audio_callback(self, in_data, frame_count, time_info, status):
        self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    async def stream_video(self, websocket):
        interval = 1.0 / self.fps
        while self.is_running:
            start_time = time.time()
            
            # Try camera, fallback to test frame
            ret, frame = self.video_cap.read()
            if not ret or frame is None:
                frame = self.generate_test_frame()
            
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            try:
                await websocket.send(buffer.tobytes())
            except Exception as e:
                print(f"Video stream error: {e}")
                break
            
            elapsed = time.time() - start_time
            await asyncio.sleep(max(0, interval - elapsed))

    async def stream_audio(self, websocket):
        if not pyaudio:
            return
        
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=self.FORMAT,
                            channels=self.CHANNELS,
                            rate=self.RATE,
                            input=True,
                            stream_callback=self.audio_callback)
            stream.start_stream()
        except Exception as e:
            print(f"Warning: Could not open microphone ({e}). Streaming silent frames.")
            stream = None

        try:
            while self.is_running:
                if stream and not self.audio_queue.empty():
                    data = self.audio_queue.get()
                else:
                    # Fallback: Send silent audio data
                    data = bytes(self.CHUNK * 2) # 2 bytes per sample for paInt16
                
                try:
                    await websocket.send(data)
                except Exception as e:
                    print(f"Audio stream error: {e}")
                    break
                await asyncio.sleep(self.CHUNK / self.RATE)
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            p.terminate()

    async def receive_messages(self, websocket):
        try:
            async for message in websocket:
                if isinstance(message, str):
                    try:
                        data = json.loads(message)
                        if "text" in data:
                            print(f"\nFUSE: {data['text']}")
                    except json.JSONDecodeError:
                        print(f"\nFUSE (Raw): {message}")
                elif isinstance(message, bytes):
                    # Audio response from Gemini
                    pass
        except websockets.ConnectionClosed:
            print("\nConnection to FUSE closed.")

    async def run(self):
        print(f"Connecting to FUSE at {self.url}...")
        try:
            # Add a timeout and keep-alive for the connection
            async with websockets.connect(self.url, ping_interval=20, ping_timeout=20) as websocket:
                print("Connected! Start brainstorming (Voice + Vision).")
                print("Press Ctrl+C to stop.")
                
                # We also need to send an initial text to trigger the session if needed
                await websocket.send(json.dumps({"text": "Hello FUSE, I am connecting from a WSL2 terminal. Can you see my test pattern?"}))

                await asyncio.gather(
                    self.stream_video(websocket),
                    self.stream_audio(websocket),
                    self.receive_messages(websocket)
                )
        except Exception as e:
            print(f"Streaming error: {e}")
        finally:
            if self.video_cap.isOpened():
                self.video_cap.release()
            self.is_running = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FUSE Multimodal Client")
    parser.add_argument("--url", default="http://localhost:8080", help="Cloud Run service URL (default: http://localhost:8080)")
    parser.add_argument("--fps", type=int, default=2, help="Frames per second (default: 2)")
    
    args = parser.parse_args()
    client = FuseMultimodalClient(args.url, args.fps)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nStopping FUSE client...")
