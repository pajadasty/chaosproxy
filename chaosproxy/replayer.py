from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from chaosproxy.utils import compute_request_signature


class ReplayMatch:
    def __init__(self, status: int, headers: Dict[str, str], body: bytes, filename: str):
        self.status = status
        self.headers = headers
        self.body = body
        self.filename = filename


class TrafficReplayer:
    def __init__(self, replay_dir: str | Path):
        self.replay_dir = Path(replay_dir)
        if not self.replay_dir.is_dir():
            raise FileNotFoundError(f"Replay directory not found: {self.replay_dir}")

        self.index_file = self.replay_dir / "index.json"
        self._exact_index: Dict[str, Path] = {}
        self._entries: List[Tuple[str, str, str, Path]] = []  # (method, path, query, file)
        self._load_fixtures()

    def _load_fixtures(self) -> None:
        json_files = list(self.replay_dir.glob("*.json"))
        for file in json_files:
            if file.name == "index.json":
                continue
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                sig = data.get("signature")
                req = data.get("request", {})
                method = req.get("method", "").upper()
                path = req.get("path", "")
                query = req.get("query", "")

                if sig:
                    self._exact_index[sig] = file
                self._entries.append((method, path, query, file))
            except Exception as e:
                print(f"[REPLAY:WARN] Could not parse fixture {file.name}: {e}")

    def find_match(self, method: str, path: str, query: str, body: bytes) -> Optional[ReplayMatch]:
        sig = compute_request_signature(method, path, query, body)

        # 1. Exact Signature Match (Method + Path + Query + Body)
        target_file = self._exact_index.get(sig)
        if not target_file:
            # 2. Fuzzy Match: Method + Path + Query
            for m, p, q, f in self._entries:
                if m == method.upper() and p == path and q == query:
                    target_file = f
                    break

        if not target_file or not target_file.is_file():
            return None

        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        resp = data.get("response", {})
        status = int(resp.get("status", 200))
        headers = dict(resp.get("headers", {}))
        body_b64 = resp.get("body_b64", "")
        body_bytes = base64.b64decode(body_b64.encode("ascii")) if body_b64 else b""

        return ReplayMatch(
            status=status,
            headers=headers,
            body=body_bytes,
            filename=target_file.name,
        )
