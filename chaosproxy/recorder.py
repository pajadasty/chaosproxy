from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from chaosproxy.utils import compute_request_signature


class TrafficRecorder:
    def __init__(self, record_dir: str | Path):
        self.record_dir = Path(record_dir)
        self.record_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.record_dir / "index.json"
        self._index: Dict[str, str] = {}
        self._load_index()

    def _load_index(self) -> None:
        if self.index_file.is_file():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except Exception:
                self._index = {}

    def _save_index(self) -> None:
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def record(
        self,
        method: str,
        path: str,
        query: str,
        request_headers: Dict[str, str],
        request_body: bytes,
        response_status: int,
        response_headers: Dict[str, str],
        response_body: bytes,
        duration_ms: int = 0,
    ) -> Path:
        sig = compute_request_signature(method, path, query, request_body)
        timestamp = datetime.now(timezone.utc).isoformat()

        # Sanitize path for file name
        safe_path = path.strip("/").replace("/", "_") or "root"
        safe_path = "".join(c for c in safe_path if c.isalnum() or c in ("-", "_"))[:40]
        filename = f"{method.upper()}_{safe_path}_{sig[:10]}.json"
        filepath = self.record_dir / filename

        entry = {
            "timestamp": timestamp,
            "signature": sig,
            "duration_ms": duration_ms,
            "request": {
                "method": method.upper(),
                "path": path,
                "query": query,
                "headers": request_headers,
                "body_b64": base64.b64encode(request_body).decode("ascii"),
            },
            "response": {
                "status": response_status,
                "headers": response_headers,
                "body_b64": base64.b64encode(response_body).decode("ascii"),
            },
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)

        self._index[sig] = filename
        self._save_index()
        return filepath
