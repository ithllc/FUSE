import redis
import json
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
        self.r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.session_id = "fuse-session-latest"

    def set_object_proxy(self, object_id: str, technical_role: str):
        """
        Maps a visual object ID to a technical role (Proxy Object Registry).
        """
        key = f"{self.session_id}:proxy_registry"
        self.r.hset(key, object_id, technical_role)

    def get_object_proxy(self, object_id: str) -> Optional[str]:
        """
        Retrieves the technical role for a visual object.
        """
        key = f"{self.session_id}:proxy_registry"
        return self.r.hget(key, object_id)

    def update_architectural_state(self, mermaid_code: str):
        """
        Saves the current Mermaid.js architectural model to Redis.
        """
        key = f"{self.session_id}:architectural_state"
        self.r.set(key, mermaid_code)

    def get_architectural_state(self) -> Optional[str]:
        """
        Retrieves the latest architectural model.
        """
        key = f"{self.session_id}:architectural_state"
        return self.r.get(key)

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """
        Logs session events for multimodal history.
        """
        import time
        key = f"{self.session_id}:events"
        self.r.lpush(key, json.dumps({
            "type": event_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": data
        }))

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieves the latest session events.
        """
        key = f"{self.session_id}:events"
        raw_events = self.r.lrange(key, 0, limit - 1)
        return [json.loads(e) for e in raw_events]

if __name__ == "__main__":
    # In a local environment, you'd need a running Redis instance (e.g. docker run --name some-redis -d redis)
    # sm = SessionStateManager()
    # sm.set_object_proxy("stapler", "GPU cluster")
    # print(sm.get_object_proxy("stapler"))
    pass
