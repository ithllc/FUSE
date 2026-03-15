# Copyright (c) 2026 ITH LLC. All rights reserved.
# Licensed under AGPL-3.0. See LICENSE file for details.

import redis
import json
import time
from typing import Dict, List, Any, Optional


class SessionStateManager:
    """
    Manages the session state using Google Cloud Memory Store (Redis).
    Stores physical object assignments and architectural state deltas.
    """
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        """
        Initializes the connection to the Redis Memory Store.
        In GCP production, 'host' will be the private IP of the Redis instance.
        """
        self.r = redis.Redis(host=host, port=port, db=db, decode_responses=True,
                              socket_timeout=3, socket_connect_timeout=3)
        self.session_id = "fuse-session-latest"

    def set_object_proxy(self, object_id: str, technical_role: str):
        """Maps a visual object ID to a technical role (Proxy Object Registry)."""
        key = f"{self.session_id}:proxy_registry"
        self.r.hset(key, object_id, technical_role)

    def get_object_proxy(self, object_id: str) -> Optional[str]:
        """Retrieves the technical role for a visual object."""
        key = f"{self.session_id}:proxy_registry"
        return self.r.hget(key, object_id)

    def get_proxy_registry(self) -> Dict[str, str]:
        """Returns full proxy registry as {object_id: technical_role} dict."""
        key = f"{self.session_id}:proxy_registry"
        return self.r.hgetall(key) or {}

    def update_architectural_state(self, mermaid_code: str):
        """Saves the current Mermaid.js architectural model to Redis."""
        key = f"{self.session_id}:architectural_state"
        self.r.set(key, mermaid_code)

    def get_architectural_state(self) -> Optional[str]:
        """Retrieves the latest architectural model."""
        key = f"{self.session_id}:architectural_state"
        return self.r.get(key)

    def get_vision_mode(self) -> str:
        """Returns current vision mode: auto|whiteboard|imagine|charades. Default: auto."""
        key = f"{self.session_id}:vision_mode"
        return self.r.get(key) or "auto"

    def set_vision_mode(self, mode: str):
        """Sets the vision processing mode."""
        key = f"{self.session_id}:vision_mode"
        self.r.set(key, mode)

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Logs session events for multimodal history."""
        key = f"{self.session_id}:events"
        self.r.lpush(key, json.dumps({
            "type": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": data
        }))

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves the latest session events."""
        key = f"{self.session_id}:events"
        raw_events = self.r.lrange(key, 0, limit - 1)
        return [json.loads(e) for e in raw_events]

    def get_recent_transcript(self, limit: int = 5) -> str:
        """Returns last N transcript events as a single string for context injection."""
        events = self.get_events(limit=limit * 3)  # Over-fetch, filter to transcript types
        transcript_events = [e for e in events if e.get("type") in ("voice_input", "proxy_assignment")]
        lines = []
        for e in transcript_events[:limit]:
            payload = e.get("payload", {})
            lines.append(payload.get("text", payload.get("role", str(payload))))
        return "\n".join(lines) if lines else ""

    def get_session_diagnostics(self) -> Dict[str, Any]:
        """Returns aggregated session state for the diagnostics UI."""
        diagnostics = {
            "vision_mode": self.get_vision_mode(),
            "proxy_count": len(self.get_proxy_registry()),
            "proxy_registry": self.get_proxy_registry(),
        }

        arch_state = self.get_architectural_state()
        diagnostics["diagram_length"] = len(arch_state) if arch_state else 0

        # Recent events with error filtering
        events = self.get_events(limit=20)
        diagnostics["total_events"] = len(events)
        diagnostics["recent_errors"] = [
            e for e in events if e.get("type") == "connection_error"
        ][:5]
        diagnostics["last_event"] = events[0] if events else None

        return diagnostics


if __name__ == "__main__":
    pass
