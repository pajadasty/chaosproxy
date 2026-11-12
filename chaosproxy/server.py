from __future__ import annotations

import time
from typing import Optional
import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

from chaosproxy.chaos import ChaosEngine
from chaosproxy.config import ProxyConfig
from chaosproxy.recorder import TrafficRecorder
from chaosproxy.replayer import TrafficReplayer
from chaosproxy.utils import (
    filter_request_headers,
    filter_response_headers,
    format_log,
)


class ChaosProxyServer:
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.chaos = ChaosEngine(config.rules)
        self.recorder = TrafficRecorder(config.record_dir) if config.record_dir else None
        self.replayer = TrafficReplayer(config.replay_dir) if config.replay_dir else None

        self.http_client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=False,  # Allow self-signed certs for local dev proxying
        )
        self.app = Starlette()
        self.app.add_route("/{path:path}", self.handle_request, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])

    async def close(self) -> None:
        await self.http_client.aclose()

    async def handle_request(self, request: Request) -> Response:
        start_time = time.perf_counter()
        method = request.method.upper()
        path = request.url.path
        query = request.url.query
        req_body = await request.body()
        req_headers = filter_request_headers(dict(request.headers))

        # 1. Check Offline Replay
        if self.replayer:
            match = self.replayer.find_match(method, path, query, req_body)
            if match:
                # Apply chaos to replay if configured
                decision = self.chaos.evaluate(method, path)
                if decision.drop:
                    if not self.config.quiet:
                        print(format_log("[CHAOS:DROP]", "---", method, path, "Dropped connection on replay"))
                    return Response(status_code=502, content=b"")

                if decision.error_status:
                    if not self.config.quiet:
                        print(format_log("[CHAOS:ERROR]", decision.error_status, method, path, "Injected error on replay"))
                    return Response(status_code=decision.error_status, content=decision.error_body or b"")

                await self.chaos.apply_latency(decision)
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)

                resp_body = match.body
                if decision.corrupt:
                    resp_body = self.chaos.corrupt_bytes(resp_body)
                    if not self.config.quiet:
                        print(format_log("[CHAOS:CORRUPT]", match.status, method, path, "Corrupted replay payload"))

                if not self.config.quiet:
                    tag = "[REPLAY]"
                    if decision.latency_ms > 0:
                        tag = f"[REPLAY:+{decision.latency_ms}ms]"
                    print(format_log(tag, match.status, method, path, f"{elapsed_ms}ms from {match.filename}"))

                return Response(
                    content=resp_body,
                    status_code=match.status,
                    headers=filter_response_headers(match.headers),
                )
            elif self.config.offline_only:
                if not self.config.quiet:
                    print(format_log("[REPLAY:MISS]", 404, method, path, "No matching fixture in offline mode"))
                return Response(
                    status_code=404,
                    content=f'{{"error": "ChaosProxy offline mode: No fixture found for {method} {path}"}}\n'.encode("utf-8"),
                    headers={"content-type": "application/json"},
                )

        # 2. Upstream forwarding requires target_url
        if not self.config.target_url:
            return Response(
                status_code=502,
                content=b'{"error": "ChaosProxy: No upstream --target configured and no replay match found"}\n',
                headers={"content-type": "application/json"},
            )

        # 3. Evaluate Chaos Rules
        decision = self.chaos.evaluate(method, path)

        # Drop simulation
        if decision.drop:
            if not self.config.quiet:
                print(format_log("[CHAOS:DROP]", "---", method, path, "Connection dropped"))
            return Response(status_code=502, content=b"")

        # Injected Error simulation
        if decision.error_status:
            if not self.config.quiet:
                print(format_log("[CHAOS:ERROR]", decision.error_status, method, path, f"Injected HTTP {decision.error_status}"))
            return Response(
                status_code=decision.error_status,
                content=decision.error_body or b"",
                headers={"content-type": "application/json"},
            )

        # Latency Jitter simulation
        await self.chaos.apply_latency(decision)

        # 4. Forward to Target Upstream
        target_base = self.config.target_url.rstrip("/")
        full_url = f"{target_base}{path}"
        if query:
            full_url = f"{full_url}?{query}"

        try:
            upstream_resp = await self.http_client.request(
                method=method,
                url=full_url,
                headers=req_headers,
                content=req_body,
            )
            resp_body = upstream_resp.content
            resp_status = upstream_resp.status_code
            resp_headers = filter_response_headers(dict(upstream_resp.headers))

        except httpx.RequestError as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            if not self.config.quiet:
                print(format_log("[UPSTREAM:ERR]", 504, method, path, f"{exc} ({elapsed_ms}ms)"))
            return Response(
                status_code=504,
                content=f'{{"error": "Upstream request failed: {str(exc)}"}}\n'.encode("utf-8"),
                headers={"content-type": "application/json"},
            )

        # 5. Corruption simulation
        if decision.corrupt:
            resp_body = self.chaos.corrupt_bytes(resp_body)
            if not self.config.quiet:
                print(format_log("[CHAOS:CORRUPT]", resp_status, method, path, "Payload corrupted"))

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 6. Record to disk if recorder is active
        if self.recorder:
            fixture_path = self.recorder.record(
                method=method,
                path=path,
                query=query,
                request_headers=req_headers,
                request_body=req_body,
                response_status=resp_status,
                response_headers=resp_headers,
                response_body=resp_body,
                duration_ms=elapsed_ms,
            )
            if not self.config.quiet:
                print(format_log("[RECORDED]", resp_status, method, path, f"{elapsed_ms}ms -> {fixture_path.name}"))
        else:
            if not self.config.quiet:
                tag = "[PROXY]"
                if decision.latency_ms > 0:
                    tag = f"[PROXY:+{decision.latency_ms}ms]"
                print(format_log(tag, resp_status, method, path, f"{elapsed_ms}ms"))

        return Response(
            content=resp_body,
            status_code=resp_status,
            headers=resp_headers,
        )
