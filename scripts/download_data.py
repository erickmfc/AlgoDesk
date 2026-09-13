"""Download closed public Binance Spot candles to a CSV on the HD."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

INTERVAL_SECONDS = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "8h": 28800,
    "12h": 43200,
    "1d": 86400,
    "3d": 259200,
    "1w": 604800,
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", choices=sorted(INTERVAL_SECONDS), default="1h")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    limit = min(max(args.limit, 1), 1000)
    query = urlencode({"symbol": args.symbol.upper(), "interval": args.interval, "limit": limit})
    request = Request(
        f"https://api.binance.com/api/v3/klines?{query}",
        headers={"User-Agent": "AlgoDesk/0.1"},
    )
    with urlopen(request, timeout=12) as response:  # noqa: S310 - fixed public Binance URL
        payload = json.load(response)
    now_ms = int(time.time() * 1000)
    interval_ms = INTERVAL_SECONDS[args.interval] * 1000
    rows = [
        row
        for row in payload
        if isinstance(row, list) and len(row) >= 7 and int(row[0]) + interval_ms <= now_ms
    ]
    output = (
        args.output
        or PROJECT_ROOT / "data" / "market" / f"{args.symbol.lower()}-{args.interval}.csv"
    )
    output = output if output.is_absolute() else PROJECT_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["open_time", "open", "high", "low", "close", "volume"])
        for row in rows:
            writer.writerow(row[:6])
    print(f"Downloaded {len(rows)} closed candles to {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
