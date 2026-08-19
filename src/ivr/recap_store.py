import json
import os
from datetime import datetime
from threading import Lock

class RecapStore:
    """Simple JSON-backed recap history store."""

    def __init__(self, path: str = "data/recap_history.json", max_items: int = 200):
        self.path = path
        self.max_items = max_items
        self._lock = Lock()
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"items": []}, f)

    def _read(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, payload):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def add_headlines(self, headlines):
        clean = [h.strip() for h in headlines if isinstance(h, str) and h.strip()]
        if not clean:
            return
        with self._lock:
            payload = self._read()
            items = payload.get("items", [])
            now = datetime.utcnow().isoformat() + "Z"
            for h in clean:
                items.append({"headline": h, "ts": now})
            payload["items"] = items[-self.max_items:]
            self._write(payload)

    def get_recent(self, limit: int = 3):
        with self._lock:
            payload = self._read()
            items = payload.get("items", [])
            return [i.get("headline", "") for i in items[-limit:] if i.get("headline")]
