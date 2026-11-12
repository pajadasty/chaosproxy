# ChaosProxy

A lightweight, asynchronous HTTP proxy and chaos engineering engine for local resilience testing, traffic recording, and offline replay.

---

## The Problem

Testing how frontends, microservices, and mobile clients behave when third-party APIs (Stripe, GitHub, AWS, payment gateways) degrade is painful:

- **What happens when Stripe throws an unexpected `502 Bad Gateway`?**
- **How does your checkout UI handle a 3.5-second latency spike?**
- **Does your JSON parser crash if an upstream API returns truncated bytes?**
- **How can automated integration tests run reliably in CI without hitting live external APIs or burning rate limits?**

`chaosproxy` sits transparently between your application and upstream services to inject deterministic chaos and record/replay real traffic offline.

---

## Features

- **Transparent HTTP Forward Proxy**: Proxies requests with streaming body support while stripping hop-by-hop headers.
- **Latency Jitter Injection**: Simulates degraded mobile networks, slow database queries, or throttled endpoints (`--latency 200-800`).
- **HTTP Error Injection**: Probabilistic failure injection (`--error-rate 0.15 --error-status 502`) to test retry logic and error boundaries.
- **Socket Drop Simulation**: Abruptly drops connections to simulate packet loss and network timeouts (`--drop-rate 0.05`).
- **Payload Corruption**: Injects malformed bytes into response payloads to verify parser resilience (`--corrupt-rate 0.05`).
- **Deterministic Traffic Recording**: Saves real request/response pairs as JSON fixtures indexed by request signature.
- **Offline Replay**: Serves recorded fixtures locally with zero network calls and deterministic response matching.
- **Per-Route Rule Configuration**: Support for multi-route rules via JSON configuration (apply errors only to `/v1/payments`, latency to `/search`, etc.).

---

## Installation

```bash
git clone https://github.com/<your-username>/chaosproxy.git
cd chaosproxy
pip install .
```

For development and running tests:

```bash
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Basic Proxy with Latency Jitter

Proxy requests to an upstream API while adding random latency between 200ms and 800ms:

```bash
chaosproxy --target https://api.github.com --port 8080 --latency 200-800
```

Point your client to `http://127.0.0.1:8080`:

```bash
curl http://127.0.0.1:8080/users/octocat
```

---

### 2. Inject 502/504 Errors on 20% of Requests

Simulate unstable upstream servers:

```bash
chaosproxy --target https://api.stripe.com --port 8080 --error-rate 0.20 --error-status 502
```

---

### 3. Record Traffic for CI / Offline Development

Record real API interactions to a local directory:

```bash
chaosproxy --target https://api.github.com --port 8080 --record ./fixtures
```

Make your requests:

```bash
curl http://127.0.0.1:8080/users/octocat
curl http://127.0.0.1:8080/users/octocat/repos
```

All interactions are saved in `./fixtures` alongside an `index.json`.

---

### 4. Offline Replay (Zero External Network Calls)

Run completely offline using recorded fixtures. If a request is not in the cache, it returns a 404:

```bash
chaosproxy --replay ./fixtures --port 8080 --offline
```

```bash
curl http://127.0.0.1:8080/users/octocat
# Returns the recorded 200 OK response instantly with identical headers and body
```

---

### 5. Advanced Multi-Route Configuration (`chaos.json`)

For complex test scenarios, configure rules per endpoint path and method:

```json
{
  "target_url": "https://api.example.com",
  "listen_port": 8080,
  "rules": [
    {
      "path_pattern": "^/v1/payments",
      "methods": ["POST"],
      "error_rate": 0.25,
      "error_status": 504,
      "error_body": "{\"error\": \"Gateway Timeout\"}"
    },
    {
      "path_pattern": "^/v1/search",
      "methods": ["GET"],
      "latency_min_ms": 500,
      "latency_max_ms": 1500
    },
    {
      "path_pattern": "^/v1/telemetry",
      "drop_rate": 0.10
    }
  ]
}
```

Run with:

```bash
chaosproxy --config chaos.json
```

---

## CLI Reference

| Flag | Description | Default |
|---|---|---|
| `-t, --target <url>` | Upstream target base URL | None |
| `-p, --port <int>` | Local port to bind to | `8080` |
| `--host <str>` | Local interface to bind to | `127.0.0.1` |
| `-c, --config <file>` | Path to JSON rule configuration | None |
| `--record <dir>` | Directory to record fixtures | None |
| `--replay <dir>` | Directory to replay fixtures from | None |
| `--offline` | Enforce offline mode (reject unrecorded paths) | `false` |
| `--latency <ms>` | Fixed ms or range (e.g. `200` or `100-500`) | None |
| `--error-rate <float>` | Error probability (`0.0` - `1.0`) | `0.0` |
| `--error-status <int>` | HTTP status for injected errors | `500` |
| `--drop-rate <float>` | Socket drop probability (`0.0` - `1.0`) | `0.0` |
| `--corrupt-rate <float>` | Payload corruption probability (`0.0` - `1.0`) | `0.0` |
| `-q, --quiet` | Silence stdout request logging | `false` |

---

## Running Tests

All core functionality is covered by automated unit and integration tests:

```bash
python -m pytest -v
```

---

## License

MIT
