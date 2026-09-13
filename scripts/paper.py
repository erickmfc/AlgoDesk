"""Read the current PAPER runtime status without placing any order."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.request import urlopen


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    with urlopen(f"{base_url}/ready", timeout=10) as response:
        ready = json.load(response)
    if ready.get("mode") != "paper":
        print(f"BLOCKED: expected PAPER, got {ready.get('mode')}")
        return 2
    with urlopen(f"{base_url}/api/paper/summary", timeout=10) as response:
        print(json.dumps(json.load(response), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
