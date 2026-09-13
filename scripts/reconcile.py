"""Run the read-only account reconciliation endpoint."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlencode
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()
    query = urlencode({"symbol": args.symbol.upper()})
    with urlopen(
        f"{args.base_url.rstrip('/')}/api/account/reconcile?{query}", timeout=60
    ) as response:
        result = json.load(response)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status") in {"SYNCED", "NOT_CONFIGURED"} else 1


if __name__ == "__main__":
    sys.exit(main())
