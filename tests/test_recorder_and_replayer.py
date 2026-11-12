import json
from pathlib import Path
import pytest
from chaosproxy.recorder import TrafficRecorder
from chaosproxy.replayer import TrafficReplayer


def test_record_and_replay_cycle(tmp_path: Path):
    recorder = TrafficRecorder(tmp_path)

    # 1. Record an HTTP exchange
    req_headers = {"authorization": "Bearer secret123", "accept": "application/json"}
    resp_headers = {"content-type": "application/json", "x-custom": "hello"}
    req_body = b'{"amount": 500, "currency": "usd"}'
    resp_body = b'{"id": "ch_123", "status": "succeeded"}'

    fixture = recorder.record(
        method="POST",
        path="/v1/charges",
        query="expand=customer",
        request_headers=req_headers,
        request_body=req_body,
        response_status=200,
        response_headers=resp_headers,
        response_body=resp_body,
        duration_ms=45,
    )

    assert fixture.is_file()
    assert (tmp_path / "index.json").is_file()

    # 2. Replay with exact match
    replayer = TrafficReplayer(tmp_path)
    match = replayer.find_match(
        method="POST",
        path="/v1/charges",
        query="expand=customer",
        body=req_body,
    )

    assert match is not None
    assert match.status == 200
    assert match.headers["x-custom"] == "hello"
    assert match.body == resp_body


def test_replay_miss_returns_none(tmp_path: Path):
    replayer = TrafficReplayer(tmp_path)
    match = replayer.find_match("GET", "/non_existent", "", b"")
    assert match is None
