"""Operational smoke/soak check for the running AlgoDesk stack.

This check is intentionally read-only: it never submits an order and refuses to
pass if the API reports a live-enabled configuration.  It is useful after a
deploy, before a Testnet soak, and as a small health probe for a VPS.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def get_json(base_url: str, path: str, timeout: float) -> object:
    request = Request(f"{base_url.rstrip('/')}{path}", headers={"Cache-Control": "no-cache"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - caller supplies local URL
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def run_cycle(base_url: str, timeout: float) -> list[Check]:
    checks: list[Check] = []
    try:
        health = get_json(base_url, "/health", timeout)
        checks.append(Check("health", health == {"status": "ok", "service": "trader"}, str(health)))
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, OSError) as exc:
        return [Check("health", False, str(exc))]

    try:
        ready = get_json(base_url, "/ready", timeout)
        if not isinstance(ready, dict):
            raise RuntimeError("readiness response is not an object")
        safe = ready.get("mode") != "live" and ready.get("live_trading_enabled") is False
        db = ready.get("database_connected") is True
        checks.append(Check("readiness", safe and db, f"mode={ready.get('mode')} db={db} live={ready.get('live_trading_enabled')}"))
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, OSError) as exc:
        checks.append(Check("readiness", False, str(exc)))

    for name, path, predicate in (
        (
            "market",
            "/api/market/ticker?symbol=BTCUSDT",
            lambda value: isinstance(value, dict)
            and value.get("source") == "binance-public-spot"
            and isinstance(value.get("tickers"), list)
            and any(
                isinstance(ticker, dict)
                and ticker.get("symbol") == "BTCUSDT"
                and float(ticker.get("price", 0)) > 0
                for ticker in value["tickers"]
            ),
        ),
        ("paper-summary", "/api/paper/summary", lambda value: isinstance(value, dict) and "status" in value),
        ("backtest", "/api/backtests/binance?symbol=BTCUSDT&interval=1h&limit=100", lambda value: isinstance(value, dict) and int(value.get("data_points", 0)) > 0),
    ):
        try:
            value = get_json(base_url, path, timeout)
            checks.append(Check(name, predicate(value), "ok" if predicate(value) else f"unexpected response: {value}"))
        except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, TypeError, OSError) as exc:
            checks.append(Check(name, False, str(exc)))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only AlgoDesk runtime verification")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cycles", type=int, default=1, help="number of samples to take")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between samples")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    if args.cycles < 1 or args.cycles > 288:
        parser.error("--cycles must be between 1 and 288")

    failed = False
    for cycle in range(args.cycles):
        checks = run_cycle(args.base_url, args.timeout)
        print(f"cycle {cycle + 1}/{args.cycles}")
        for check in checks:
            print(f"  {'PASS' if check.ok else 'FAIL'} {check.name}: {check.detail}")
        failed = failed or any(not check.ok for check in checks)
        if cycle + 1 < args.cycles:
            time.sleep(args.interval)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
