"""Public, read-only Binance Spot market adapter."""
from dataclasses import dataclass
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Ticker:
    symbol: str
    price: float


class BinancePublicClient:
    def __init__(self, base_url: str = "https://api.binance.com") -> None:
        self.base_url = base_url.rstrip("/")

    def ticker_price(self, symbols: list[str]) -> list[Ticker]:
        query = urlencode({"symbols": json.dumps([symbol.upper() for symbol in symbols], separators=(",", ":"))})
        request = Request(f"{self.base_url}/api/v3/ticker/price?{query}", headers={"User-Agent": "AlgoDesk/0.1"})
        with urlopen(request, timeout=8) as response:  # noqa: S310 - fixed Binance HTTPS endpoint
            payload = json.load(response)
        if isinstance(payload, dict):
            payload = [payload]
        return [Ticker(str(row["symbol"]), float(row["price"])) for row in payload]

    def exchange_info(self, symbol: str) -> dict[str, object]:
        query = urlencode({"symbol": symbol.upper()})
        request = Request(f"{self.base_url}/api/v3/exchangeInfo?{query}", headers={"User-Agent": "AlgoDesk/0.1"})
        with urlopen(request, timeout=8) as response:  # noqa: S310 - fixed Binance HTTPS endpoint
            return json.load(response)
