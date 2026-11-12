import asyncio
from pathlib import Path
import httpx

from chaosproxy.config import ChaosRule, ProxyConfig
from chaosproxy.recorder import TrafficRecorder
from chaosproxy.server import ChaosProxyServer


def test_offline_replay_server(tmp_path: Path):
    async def _run():
        recorder = TrafficRecorder(tmp_path)
        recorder.record(
            method="GET",
            path="/v1/status",
            query="",
            request_headers={},
            request_body=b"",
            response_status=200,
            response_headers={"content-type": "application/json"},
            response_body=b'{"healthy": true}',
        )

        config = ProxyConfig(
            replay_dir=tmp_path,
            offline_only=True,
            quiet=True,
        )
        server = ChaosProxyServer(config)

        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/v1/status")
            assert response.status_code == 200
            assert response.json() == {"healthy": True}

            missing_resp = await client.get("/v1/unknown")
            assert missing_resp.status_code == 404

        await server.close()

    asyncio.run(_run())


def test_chaos_error_injection_through_server(tmp_path: Path):
    async def _run():
        recorder = TrafficRecorder(tmp_path)
        recorder.record(
            method="POST",
            path="/v1/orders",
            query="",
            request_headers={},
            request_body=b'{"item": "book"}',
            response_status=201,
            response_headers={"content-type": "application/json"},
            response_body=b'{"order_id": 999}',
        )

        rule = ChaosRule(
            path_pattern="^/v1/orders",
            methods=["POST"],
            error_rate=1.0,
            error_status=503,
            error_body='{"error": "Service Unavailable - Overloaded"}',
        )

        config = ProxyConfig(
            replay_dir=tmp_path,
            rules=[rule],
            quiet=True,
        )
        server = ChaosProxyServer(config)

        transport = httpx.ASGITransport(app=server.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/v1/orders", content=b'{"item": "book"}')
            assert response.status_code == 503
            assert "Service Unavailable" in response.text

        await server.close()

    asyncio.run(_run())
