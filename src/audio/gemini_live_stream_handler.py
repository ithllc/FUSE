import os
import asyncio
from typing import Optional
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


class GeminiLiveStreamHandler:
    """
    Interleaves audio transcripts with vision frame metadata using Gemini 3.1 Flash Live.
    Designed for real-time gesture tracking and multimodal technical intent detection.
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

    def get_config(self) -> types.LiveConnectConfig:
        """Returns the configuration for the Gemini 3.1 Flash Live session."""
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[
                    types.Part.from_text(
                        text=(
                            "You are FUSE, the Collaborative Brainstorming Intelligence. "
                            "You are an expert system architect and facilitator. "
                            "You use vision and audio to help users design complex systems. "
                            "IMPORTANT: When the session begins, immediately greet the user by saying: "
                            "'Hello! I am FUSE, your brainstorming assistant. "
                            "Let me run a quick check. Please say a few words to test your microphone.' "
                            "Do not wait for the user to speak first — start talking right away. "
                            "When you hear the user speak, respond with: "
                            "'I can hear you clearly. Let us begin your brainstorming session.' "
                            "After this initial greeting and mic check, proceed normally. "
                            "When a user assigns a role to an object (e.g., 'This stapler is a GPU'), "
                            "acknowledge it and maintain context. "
                            "If you see a technical sketch, you'll help extract it into Mermaid.js. "
                            "Interrupt only if you detect a logical architecture violation or "
                            "if the user asks for a validation check. "
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
