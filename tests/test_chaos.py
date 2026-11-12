import pytest
from chaosproxy.chaos import ChaosEngine
from chaosproxy.config import ChaosRule


def test_rule_matching():
    rule = ChaosRule(
        path_pattern=r"^/api/v1/checkout",
        methods=["POST"],
        error_rate=1.0,
        error_status=503,
    )
    assert rule.matches("POST", "/api/v1/checkout") is True
    assert rule.matches("GET", "/api/v1/checkout") is False
    assert rule.matches("POST", "/api/v1/users") is False


def test_error_injection_deterministic():
    rule = ChaosRule(
        path_pattern=".*",
        error_rate=1.0,
        error_status=504,
        error_body='{"error": "timeout"}',
    )
    engine = ChaosEngine([rule])
    decision = engine.evaluate("GET", "/test")
    assert decision.error_status == 504
    assert decision.error_body == b'{"error": "timeout"}'


def test_connection_drop_deterministic():
    rule = ChaosRule(
        path_pattern=".*",
        drop_rate=1.0,
    )
    engine = ChaosEngine([rule])
    decision = engine.evaluate("GET", "/test")
    assert decision.drop is True


def test_latency_jitter():
    rule = ChaosRule(
        path_pattern=".*",
        latency_min_ms=100,
        latency_max_ms=200,
    )
    engine = ChaosEngine([rule])
    decision = engine.evaluate("GET", "/test")
    assert 100 <= decision.latency_ms <= 200


def test_payload_corruption():
    engine = ChaosEngine([])
    original = b'{"status": "ok", "balance": 1000}'
    corrupted = engine.corrupt_bytes(original)
    assert corrupted != original
    assert len(corrupted) > 0
