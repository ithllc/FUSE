# Copyright (c) 2026 ITH LLC. All rights reserved.
# Licensed under AGPL-3.0. See LICENSE file for details.

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
        # Vertex AI Live API model — GA model (hackathon-compatible)
        # Preview tested in issue #27: 53s+ latency, worse than GA. Reverting.
        self.model_id = "gemini-live-2.5-flash-native-audio"

    def get_config(self, resumption_handle: str = None) -> types.LiveConnectConfig:
        """Returns the configuration for the Gemini Live session.

        Args:
            resumption_handle: Optional handle from a previous session for seamless
                reconnection. Pass None for the first connection.
        """
        # Issue #29 fix: minimal config + session_resumption + compression + VAD.
        # - transparent=True: Vertex AI feature for seamless reconnection indexing
        #   (confirmed: cloud.google.com/vertex-ai/generative-ai/docs/live-api/start-manage-session)
        # - RealtimeInputConfig: server-side VAD prevents 1007 from audio arriving
        #   during session transitions (replaces 0.5s sleep hacks in main.py)
        #   (confirmed: ai.google.dev/gemini-api/docs/live-guide)
        # - context_window_compression: audio at ~25 tok/s exhausts 128k in ~85 min
        #   (confirmed: ai.google.dev/gemini-api/docs/live-api/best-practices)
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            ),
            # Session resumption: survives Gemini server-side connection resets.
            # transparent=True returns client message index for seamless resend.
            session_resumption=types.SessionResumptionConfig(
                handle=resumption_handle,
                transparent=True,
            ),
            # Context window compression: prevents token exhaustion.
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
            # Server-side VAD: Gemini manages speech boundaries, preventing
            # 1007 errors from audio frames hitting during turn transitions.
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                )
            ),
        )

    def get_full_config(self, resumption_handle: str = None) -> types.LiveConnectConfig:
        """Full FUSE config with all features. Disabled until minimal config passes.

        Re-enable by swapping get_config() back to this implementation.
        """
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck"
                    )
                )
            ),
            proactivity=types.ProactivityConfig(proactive_audio=True),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            session_resumption=types.SessionResumptionConfig(
                handle=resumption_handle
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow(),
            ),
            tools=LIVE_TOOLS,
            system_instruction=types.Content(
                parts=[
                    types.Part.from_text(
                        text=(
                            "You are FUSE, an expert system architect and brainstorming facilitator. "
                            "You help users design complex systems using voice and vision. "
                            "Keep your responses concise. "
                            "When the session begins, greet the user and ask them to say a few words "
                            "to test their microphone. "
                            "\n\n"
                            "TOOLS: Use capture_and_analyze_frame when the user references something "
                            "visual. Use set_proxy_object when a user assigns a role to a physical "
                            "object. Use get_session_context to recall current state."
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
