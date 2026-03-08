import cv2
import asyncio
import websockets
import json
import base64
import time
import argparse
import threading
import queue

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

    def audio_callback(self, in_data, frame_count, time_info, status):
        self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    async def stream_video(self, websocket):
        interval = 1.0 / self.fps
        while self.is_running:
            start_time = time.time()
            ret, frame = self.video_cap.read()
            if ret:
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                # In a real multimodal stream, you'd interleave frames with audio
                # For this simplified client, we send frames as binary messages
                await websocket.send(buffer.tobytes())
            
            elapsed = time.time() - start_time
            await asyncio.sleep(max(0, interval - elapsed))

    async def stream_audio(self, websocket):
        if not pyaudio:
            return
        
        p = pyaudio.PyAudio()
        stream = p.open(format=self.FORMAT,
                        channels=self.CHANNELS,
                        rate=self.RATE,
                        input=True,
                        stream_callback=self.audio_callback)

        stream.start_stream()
        try:
            while self.is_running:
                if not self.audio_queue.empty():
                    data = self.audio_queue.get()
                    await websocket.send(data)
                await asyncio.sleep(0.01)
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    async def receive_messages(self, websocket):
        try:
            async for message in websocket:
                if isinstance(message, str):
                    data = json.loads(message)
                    if "text" in data:
                        print(f"FUSE: {data['text']}")
                elif isinstance(message, bytes):
                    # In a full implementation, you'd play this audio back
                    # print("Received audio response from FUSE...")
                    pass
        except websockets.ConnectionClosed:
            print("Connection to FUSE closed.")

    async def run(self):
        print(f"Connecting to FUSE at {self.url}...")
        try:
            async with websockets.connect(self.url) as websocket:
                print("Connected! Start brainstorming (Voice + Vision).")
                print("Press Ctrl+C to stop.")
                
                await asyncio.gather(
                    self.stream_video(websocket),
                    self.stream_audio(websocket),
                    self.receive_messages(websocket)
                )
        except Exception as e:
            print(f"Streaming error: {e}")
        finally:
            self.video_cap.release()
            self.is_running = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FUSE Multimodal Client")
    parser.add_argument("--url", required=True, help="Cloud Run service URL (e.g., https://fuse-...)")
    parser.add_argument("--fps", type=int, default=2, help="Frames per second (default: 2)")
    
    args = parser.parse_args()
    client = FuseMultimodalClient(args.url, args.fps)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nStopping FUSE client...")
