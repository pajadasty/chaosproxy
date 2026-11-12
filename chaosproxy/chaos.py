from __future__ import annotations

import asyncio
import random
from typing import List, Optional, Tuple
from chaosproxy.config import ChaosRule


class ChaosDecision:
    def __init__(
        self,
        drop: bool = False,
        error_status: Optional[int] = None,
        error_body: Optional[bytes] = None,
        latency_ms: int = 0,
        corrupt: bool = False,
        rule_matched: Optional[ChaosRule] = None,
    ):
        self.drop = drop
        self.error_status = error_status
        self.error_body = error_body
        self.latency_ms = latency_ms
        self.corrupt = corrupt
        self.rule_matched = rule_matched


class ChaosEngine:
    def __init__(self, rules: List[ChaosRule]):
        self.rules = rules

    def evaluate(self, method: str, path: str) -> ChaosDecision:
        for rule in self.rules:
            if not rule.matches(method, path):
                continue

            # 1. Connection Drop check
            if rule.drop_rate > 0.0 and random.random() < rule.drop_rate:
                return ChaosDecision(drop=True, rule_matched=rule)

            # 2. HTTP Error Injection check
            if rule.error_rate > 0.0 and random.random() < rule.error_rate:
                body = (
                    rule.error_body.encode("utf-8")
                    if rule.error_body
                    else f'{{"error": "ChaosProxy injected {rule.error_status}"}}\n'.encode("utf-8")
                )
                return ChaosDecision(
                    error_status=rule.error_status,
                    error_body=body,
                    rule_matched=rule,
                )

            # 3. Latency Jitter
            latency_ms = 0
            if rule.latency_max_ms > 0:
                min_lat = max(0, rule.latency_min_ms)
                max_lat = max(min_lat, rule.latency_max_ms)
                latency_ms = random.randint(min_lat, max_lat)

            # 4. Payload Corruption check
            corrupt = rule.corrupt_rate > 0.0 and random.random() < rule.corrupt_rate

            return ChaosDecision(
                latency_ms=latency_ms,
                corrupt=corrupt,
                rule_matched=rule,
            )

        return ChaosDecision()

    async def apply_latency(self, decision: ChaosDecision) -> None:
        if decision.latency_ms > 0:
            await asyncio.sleep(decision.latency_ms / 1000.0)

    @staticmethod
    def corrupt_bytes(data: bytes) -> bytes:
        if not data:
            return b"CORRUPTED_CHAOS_EMPTY"
        # Truncate halfway or scramble bytes
        cut_point = max(1, len(data) // 2)
        corrupted = bytearray(data[:cut_point])
        # Append corrupt control sequence
        corrupted.extend(b"\x00\xFF\xFE<MALFORMED_CHAOS_BYTE_STREAM>")
        return bytes(corrupted)
