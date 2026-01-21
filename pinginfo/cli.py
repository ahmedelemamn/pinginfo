"""CLI entrypoint for PingInfo."""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Sequence

from pinginfo.ping import ping_hosts


def _format_latency(latency_ms: float | None) -> str:
    if latency_ms is None:
        return "-"
    return f"{latency_ms:.1f} ms"


def _print_table(results, iteration: int) -> None:
    header = f"PingInfo - iteration {iteration}"
    print("\n" + header)
    print("=" * len(header))
    print(f"{'Host':<30} {'Status':<12} {'Latency':>10} {'Reverse':<30}")
    print("-" * 86)
    for result in results:
        status = "OK" if result.success else "FAIL"
        reverse = result.reverse_name or "-"
        print(
            f"{result.host:<30} {status:<12} {_format_latency(result.latency_ms):>10} {reverse:<30}"
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ping multiple hosts concurrently.")
    parser.add_argument("--hosts", nargs="+", required=True, help="Hosts to ping")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between runs")
    parser.add_argument("--timeout", type=float, default=1.5, help="Ping timeout in seconds")
    parser.add_argument("--count", type=int, default=0, help="Number of iterations (0 = forever)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    iteration = 0
    try:
        while True:
            iteration += 1
            results = asyncio.run(ping_hosts(args.hosts, args.timeout))
            _print_table(results, iteration)
            if args.count and iteration >= args.count:
                break
            time.sleep(max(args.interval, 0))
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
