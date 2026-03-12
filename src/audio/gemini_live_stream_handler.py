import os
import asyncio
from typing import Optional, List, Dict
from google import genai
from google.genai import types

from src.state.session_state_manager import SessionStateManager


# Voice command keywords for vision mode switching (Phase 4)
MODE_KEYWORDS = {
    "whiteboard mode": "whiteboard",
    "sketch mode": "whiteboard",
    "imagine mode": "imagine",
    "object mode": "imagine",
    "proxy mode": "imagine",
    "charades mode": "charades",
    "gesture mode": "charades",
    "auto mode": "auto",
}

# Function declarations for Live API tool use (issue #19)
LIVE_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "capture_and_analyze_frame",
                "description": (
                    "Captures the latest camera frame and analyzes it through the "
                    "vision pipeline. Use this when the user asks you to look at, "
                    "describe, or analyze what the camera sees (e.g., 'do you see "
                    "the whiteboard?', 'what objects are on the table?', 'look at "
                    "this sketch'). Returns the scene type, any extracted Mermaid "
                    "diagram code, and a description of what was found."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["auto", "whiteboard", "imagine", "charades"],
                            "description": (
                                "Vision processing mode. Use 'whiteboard' when the "
                                "user mentions a whiteboard or sketch. Use 'imagine' "
                                "when the user asks about physical objects on a table. "
                                "Use 'charades' when the user is gesturing. Use 'auto' "
                                "to let the system detect the scene type automatically."
                            ),
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "get_session_context",
                "description": (
                    "Retrieves the current session state including proxy object "
                    "assignments, the current architecture diagram, and recent "
                    "transcript history. Use this when you need to recall what "
                    "objects have been assigned, what the current architecture "
                    "looks like, or what was discussed recently."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "set_proxy_object",
                "description": (
                    "Registers a physical object as a proxy for an architecture "
                    "component. Use this when the user assigns a role to an object "
                    "(e.g., 'this stapler is our load balancer', 'the cup is the "
                    "database'). This updates the proxy registry used by the vision "
                    "pipeline."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_name": {
                            "type": "string",
                            "description": "The physical object being assigned (e.g., 'stapler', 'cup', 'phone').",
                        },
                        "technical_role": {
                            "type": "string",
                            "description": "The architecture component it represents (e.g., 'load balancer', 'database', 'API gateway').",
                        },
                    },
                    "required": ["object_name", "technical_role"],
                },
            },
        ]
    }
]


class GeminiLiveStreamHandler:
    """
    Handles bidirectional audio streaming via Gemini Live API with function calling
    for on-demand vision capture. Designed for real-time gesture tracking and
    multimodal technical intent detection.
    """
    def __init__(self, project_id: str, state_manager: SessionStateManager, location: str = "global"):
        self.project_id = project_id
        self.location = location
        self.state_manager = state_manager
        # Live API on Vertex AI requires us-central1 (not "global")
        live_location = "us-central1" if location == "global" else location
        self.client = genai.Client(
            vertexai=True,
            project=project_id,
            location=live_location,
            http_options={"api_version": "v1beta1"}
        )
        # Vertex AI Live API model (GA)
        self.model_id = "gemini-live-2.5-flash-native-audio"

    def get_config(self, resumption_handle: str = None) -> types.LiveConnectConfig:
        """Returns the configuration for the Gemini Live session.

        Args:
            resumption_handle: Optional handle from a previous session for seamless
                reconnection. Pass None for the first connection.
        """
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            proactivity=types.ProactivityConfig(proactive_audio=True),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            # Session resumption: survives Gemini server-side connection resets.
            # Tokens are valid for 2 hours (Vertex AI) after last session end.
            session_resumption=types.SessionResumptionConfig(
                handle=resumption_handle
            ),
            # Context window compression: prevents 128k token exhaustion.
            # Without this, audio-only sessions are limited to ~15 minutes.
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
            # Function calling tools for on-demand vision capture (issue #19)
            tools=LIVE_TOOLS,
            system_instruction=types.Content(
                parts=[
                    types.Part.from_text(
                        text=(
                            "You are FUSE, the Collaborative Brainstorming Intelligence. "
                            "You are an expert system architect and facilitator. "
                            "You help users design complex systems using voice and vision. "
                            "IMPORTANT: When the session begins, immediately greet the user by saying: "
                            "'Hello! I am FUSE, your brainstorming assistant. "
                            "Let me run a quick check. Please say a few words to test your microphone.' "
                            "Do not wait for the user to speak first — start talking right away. "
                            "When you hear the user speak, respond with: "
                            "'I can hear you clearly. Let us begin your brainstorming session.' "
                            "After this initial greeting and mic check, proceed normally. "
                            "\n\n"
                            "VISION CAPABILITIES: You have access to a camera through the "
                            "capture_and_analyze_frame function. When a user asks you to look at "
                            "something, see the whiteboard, describe objects, or analyze what's in "
                            "front of them, call this function to capture and analyze the current "
                            "camera frame. Describe what the vision system found in your audio response. "
                            "\n\n"
                            "PROXY OBJECTS: When a user assigns a role to a physical object "
                            "(e.g., 'This stapler is a GPU'), call set_proxy_object to register it. "
                            "You can also call get_session_context to recall all current assignments "
                            "and the architecture diagram state. "
                            "\n\n"
                            "When you detect a logical architecture violation or the user asks for "
                            "a validation check, let them know. "
                            "When a user requests a mode switch (e.g., 'switch to whiteboard mode'), "
                            "acknowledge the switch."
                        )
                    )
                ]
            )
        )

    async def start_session(self):
        """Starts a multimodal live session."""
        try:
            async with self.client.aio.live.connect(
                model=self.model_id,
                config=types.LiveConnectConfig(
                    response_modalities=["AUDIO"]
                )
            ) as session:
                print("Live session connected. Ready for gesture and voice commands.")
                while True:
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"Live session error: {e}")

    async def process_simulated_command(self, text: str):
        """
        Processes text commands for proxy object assignment and vision mode switching.
        """
        print(f"Processing command: {text}")
        text_lower = text.lower()

        # Check for vision mode switch commands (Phase 4)
        for phrase, mode in MODE_KEYWORDS.items():
            if phrase in text_lower:
                self.state_manager.set_vision_mode(mode)
                self.state_manager.log_event("mode_switch", {"mode": mode})
                return f"Switched to {mode} mode."

        # Proxy object assignment
        if "is our" in text_lower or "is a" in text_lower:
            parts = text_lower.split(" is ")
            obj_name = parts[0].replace("this ", "").strip()
            role = parts[1].replace("our ", "").replace("a ", "").strip()

            self.state_manager.set_object_proxy(obj_name, role)
            print(f"Proxy registered: {obj_name} -> {role}")
            self.state_manager.log_event("proxy_assignment", {"object": obj_name, "role": role})
            return f"Understood. {obj_name} is now the {role}."

        return "Command not recognized."

    async def _handle_message(self, message):
        """Processes incoming multimodal messages from the live session."""
        pass


if __name__ == "__main__":
    pass
