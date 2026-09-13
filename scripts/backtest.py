"""Run the auditable Binance backtest through the local read-only API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="1h")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    query = urlencode(
        {
            "symbol": args.symbol.upper(),
            "interval": args.interval,
            "limit": min(max(args.limit, 100), 1000),
        }
    )
    with urlopen(
        f"{args.base_url.rstrip('/')}/api/backtests/binance?{query}", timeout=60
    ) as response:
        result = json.load(response)
    output = args.output
    if output is not None:
        output = output if output.is_absolute() else PROJECT_ROOT / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Backtest report written to {output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
