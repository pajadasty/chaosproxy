from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ChaosRule:
    path_pattern: str = ".*"
    methods: List[str] = field(default_factory=list)
    latency_min_ms: int = 0
    latency_max_ms: int = 0
    error_rate: float = 0.0
    error_status: int = 500
    error_body: Optional[str] = None
    drop_rate: float = 0.0
    corrupt_rate: float = 0.0

    def matches(self, method: str, path: str) -> bool:
        if self.methods and method.upper() not in [m.upper() for m in self.methods]:
            return False
        return bool(re.search(self.path_pattern, path))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChaosRule:
        return cls(
            path_pattern=data.get("path_pattern", ".*"),
            methods=data.get("methods", []),
            latency_min_ms=int(data.get("latency_min_ms", 0)),
            latency_max_ms=int(data.get("latency_max_ms", 0)),
            error_rate=float(data.get("error_rate", 0.0)),
            error_status=int(data.get("error_status", 500)),
            error_body=data.get("error_body"),
            drop_rate=float(data.get("drop_rate", 0.0)),
            corrupt_rate=float(data.get("corrupt_rate", 0.0)),
        )


@dataclass
class ProxyConfig:
    target_url: Optional[str] = None
    listen_host: str = "127.0.0.1"
    listen_port: int = 8080
    record_dir: Optional[Path] = None
    replay_dir: Optional[Path] = None
    offline_only: bool = False
    rules: List[ChaosRule] = field(default_factory=list)
    quiet: bool = False

    @classmethod
    def from_file(cls, path: str | Path) -> ProxyConfig:
        config_path = Path(path)
        if not config_path.is_file():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        rules = [ChaosRule.from_dict(r) for r in data.get("rules", [])]
        record_dir = Path(data["record_dir"]) if data.get("record_dir") else None
        replay_dir = Path(data["replay_dir"]) if data.get("replay_dir") else None

        return cls(
            target_url=data.get("target_url"),
            listen_host=data.get("listen_host", "127.0.0.1"),
            listen_port=int(data.get("listen_port", 8080)),
            record_dir=record_dir,
            replay_dir=replay_dir,
            offline_only=bool(data.get("offline_only", False)),
            rules=rules,
            quiet=bool(data.get("quiet", False)),
        )
