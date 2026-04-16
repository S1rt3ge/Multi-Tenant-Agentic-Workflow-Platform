#!/usr/bin/env python3
"""Simple API SLO checker for key endpoints.

Usage:
  python scripts/check-api-slo.py --base-url http://localhost:8000 --max-health-ms 1000 --max-ready-ms 1500
"""

from __future__ import annotations

import argparse
import json
import http.client
import sys
import time
from urllib import error, request


def fetch(url: str) -> tuple[int, float, str]:
    start = time.perf_counter()
    try:
        with request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.getcode() or 0
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except Exception as exc:  # pragma: no cover
        elapsed_ms = (time.perf_counter() - start) * 1000
        if isinstance(exc, http.client.RemoteDisconnected):
            return 503, elapsed_ms, "remote disconnected during warmup"
        return 0, elapsed_ms, str(exc)

    elapsed_ms = (time.perf_counter() - start) * 1000
    return status, elapsed_ms, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Check API SLO for health/ready endpoints")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--max-health-ms", type=float, default=1000)
    parser.add_argument("--max-ready-ms", type=float, default=1500)
    args = parser.parse_args()

    checks = [
        ("health", f"{args.base_url}/health", args.max_health_ms),
        ("ready", f"{args.base_url}/ready", args.max_ready_ms),
    ]

    failures: list[str] = []
    output = []

    startup_delay_seconds = 5
    time.sleep(startup_delay_seconds)

    for name, url, max_ms in checks:
        status, elapsed_ms, body = fetch(url)
        if status in (0, 503):
            # allow short warm-up retries for newly started containers
            for _ in range(4):
                time.sleep(1)
                status, elapsed_ms, body = fetch(url)
                if status not in (0, 503):
                    break
        ok = status == 200 and elapsed_ms <= max_ms
        output.append(
            {
                "endpoint": name,
                "url": url,
                "status": status,
                "latency_ms": round(elapsed_ms, 2),
                "max_ms": max_ms,
                "ok": ok,
            }
        )

        if status != 200:
            failures.append(f"{name}: expected status 200, got {status}. body={body[:300]}")
        if elapsed_ms > max_ms:
            failures.append(f"{name}: latency {elapsed_ms:.2f}ms exceeds SLO {max_ms:.2f}ms")

    print(json.dumps({"checks": output}, ensure_ascii=True))

    if failures:
        for failure in failures:
            print(f"SLO failure: {failure}", file=sys.stderr)
        return 1

    print("SLO checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
