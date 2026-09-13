"""Read-only runtime soak test for AlgoDesk.

Use PAPER for local stability checks. Use --require-mode testnet only after
Testnet credentials are configured; this script never places an order itself.
"""

from __future__ import annotations

import argparse
import sys
import time

from verify_runtime import get_json, run_cycle


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only AlgoDesk runtime soak test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cycles", type=int, default=12)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--require-mode", choices=("paper", "testnet"), default="paper")
    args = parser.parse_args()
    if args.cycles < 1 or args.cycles > 288:
        parser.error("--cycles must be between 1 and 288")

    try:
        ready = get_json(args.base_url, "/ready", 10)
    except Exception as exc:  # noqa: BLE001 - present a concise operator error
        print(f"BLOCKED readiness: {exc}")
        return 2
    if not isinstance(ready, dict) or ready.get("mode") != args.require_mode:
        print(f"BLOCKED mode: expected {args.require_mode}, got {ready.get('mode') if isinstance(ready, dict) else ready}")
        return 2
    if args.require_mode == "testnet" and ready.get("account_configured") is not True:
        print("BLOCKED credentials: Binance Testnet API credentials are not configured")
        return 2

    failed = False
    for cycle in range(args.cycles):
        checks = run_cycle(args.base_url, 10)
        failed = failed or any(not check.ok for check in checks)
        print(f"soak cycle {cycle + 1}/{args.cycles}: {'PASS' if not any(not check.ok for check in checks) else 'FAIL'}")
        if failed:
            for check in checks:
                if not check.ok:
                    print(f"  FAIL {check.name}: {check.detail}")
            break
        if cycle + 1 < args.cycles:
            time.sleep(args.interval)
    print("SOAK PASS" if not failed else "SOAK FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
