from __future__ import annotations

import argparse
import sys
from pathlib import Path
import uvicorn

from chaosproxy import __version__
from chaosproxy.config import ChaosRule, ProxyConfig
from chaosproxy.server import ChaosProxyServer


def parse_latency_arg(arg: str) -> tuple[int, int]:
    if "-" in arg:
        parts = arg.split("-")
        return int(parts[0]), int(parts[1])
    val = int(arg)
    return val, val


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chaosproxy",
        description="Local HTTP traffic recorder, replay engine, and network chaos injector.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    parser.add_argument(
        "-t", "--target",
        dest="target",
        help="Upstream target URL to proxy (e.g. https://api.stripe.com)",
    )
    parser.add_argument(
        "-p", "--port",
        dest="port",
        type=int,
        default=8888,
        help="Local port to bind to (default: 8888)",
    )
    parser.add_argument(
        "--host",
        dest="host",
        default="127.0.0.1",
        help="Local interface to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "-c", "--config",
        dest="config",
        help="Path to JSON configuration file for multi-route chaos rules",
    )
    parser.add_argument(
        "--record",
        dest="record_dir",
        help="Directory to record request/response fixtures",
    )
    parser.add_argument(
        "--replay",
        dest="replay_dir",
        help="Directory to replay recorded fixtures from (supports offline mode)",
    )
    parser.add_argument(
        "--offline",
        dest="offline",
        action="store_true",
        help="Fail with 404 if incoming request has no matching recorded fixture",
    )
    parser.add_argument(
        "--latency",
        dest="latency",
        help="Add latency in ms. Can be single value (e.g. 500) or range (e.g. 200-800)",
    )
    parser.add_argument(
        "--error-rate",
        dest="error_rate",
        type=float,
        default=0.0,
        help="Probability of injecting an HTTP error (0.0 to 1.0)",
    )
    parser.add_argument(
        "--error-status",
        dest="error_status",
        type=int,
        default=500,
        help="HTTP status code for injected errors (default: 500)",
    )
    parser.add_argument(
        "--drop-rate",
        dest="drop_rate",
        type=float,
        default=0.0,
        help="Probability of dropping connection (0.0 to 1.0)",
    )
    parser.add_argument(
        "--corrupt-rate",
        dest="corrupt_rate",
        type=float,
        default=0.0,
        help="Probability of corrupting response payload (0.0 to 1.0)",
    )
    parser.add_argument(
        "-q", "--quiet",
        dest="quiet",
        action="store_true",
        help="Disable stdout request logging",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.config:
        config = ProxyConfig.from_file(args.config)
    else:
        if not args.target and not args.replay_dir:
            parser.error("You must specify either --target <url> or --replay <dir> (or provide --config)")

        rules = []
        lat_min, lat_max = (0, 0)
        if args.latency:
            try:
                lat_min, lat_max = parse_latency_arg(args.latency)
            except ValueError:
                parser.error("Invalid --latency format. Use e.g. 300 or 100-500")

        # Global chaos rule from CLI flags
        if lat_max > 0 or args.error_rate > 0 or args.drop_rate > 0 or args.corrupt_rate > 0:
            rules.append(
                ChaosRule(
                    path_pattern=".*",
                    latency_min_ms=lat_min,
                    latency_max_ms=lat_max,
                    error_rate=args.error_rate,
                    error_status=args.error_status,
                    drop_rate=args.drop_rate,
                    corrupt_rate=args.corrupt_rate,
                )
            )

        config = ProxyConfig(
            target_url=args.target,
            listen_host=args.host,
            listen_port=args.port,
            record_dir=Path(args.record_dir) if args.record_dir else None,
            replay_dir=Path(args.replay_dir) if args.replay_dir else None,
            offline_only=args.offline,
            rules=rules,
            quiet=args.quiet,
        )

    print(f"\033[1m\033[36mChaosProxy v{__version__}\033[0m")
    if config.target_url:
        print(f"  Target:   \033[32m{config.target_url}\033[0m")
    if config.record_dir:
        print(f"  Record:   \033[33m{config.record_dir.resolve()}\033[0m")
    if config.replay_dir:
        print(f"  Replay:   \033[35m{config.replay_dir.resolve()} (offline={config.offline_only})\033[0m")
    if config.rules:
        r = config.rules[0]
        chaos_desc = []
        if r.latency_max_ms > 0:
            chaos_desc.append(f"Latency {r.latency_min_ms}-{r.latency_max_ms}ms")
        if r.error_rate > 0:
            chaos_desc.append(f"Errors {int(r.error_rate*100)}% ({r.error_status})")
        if r.drop_rate > 0:
            chaos_desc.append(f"Drops {int(r.drop_rate*100)}%")
        if r.corrupt_rate > 0:
            chaos_desc.append(f"Corruption {int(r.corrupt_rate*100)}%")
        if chaos_desc:
            print(f"  Chaos:    \033[31m{', '.join(chaos_desc)}\033[0m")

    print(f"  Listening:\033[1m http://{config.listen_host}:{config.listen_port}\033[0m\n")

    proxy_server = ChaosProxyServer(config)
    uvicorn_config = uvicorn.Config(
        proxy_server.app,
        host=config.listen_host,
        port=config.listen_port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(uvicorn_config)
    try:
        server.run()
    except KeyboardInterrupt:
        print("\n[CHAOSPROXY] Shutting down...")


if __name__ == "__main__":
    main()
