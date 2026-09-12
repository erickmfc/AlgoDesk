"""Binance Spot adapters for public market data and optional read-only account data."""
import asyncio
from dataclasses import dataclass
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import websockets


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


class BinancePrivateClient(BinancePublicClient):
    """Signed account reader. It deliberately has no order-writing methods."""

    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://api.binance.com") -> None:
        super().__init__(base_url)
        self.api_key = api_key.strip()
        self.api_secret = api_secret

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def account_information(self) -> dict[str, object]:
        if not self.configured:
            raise RuntimeError("Binance account credentials are not configured")
        params = {"omitZeroBalances": "true", "recvWindow": "5000", "timestamp": str(int(time.time() * 1000))}
        query = urlencode(params)
        signature = hmac.new(self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        request = Request(
            f"{self.base_url}/api/v3/account?{query}&signature={signature}",
            headers={"User-Agent": "AlgoDesk/0.1", "X-MBX-APIKEY": self.api_key},
        )
        with urlopen(request, timeout=8) as response:  # noqa: S310 - fixed Binance HTTPS endpoint
            payload = json.load(response)
        if not isinstance(payload, dict):
            raise ValueError("unexpected Binance account response")
        return payload


class BinanceMarketStream:
    """Public mini-ticker stream with reconnect, backoff and built-in heartbeat."""

    def __init__(self, base_url: str = "wss://stream.binance.com:9443/stream") -> None:
        self.base_url = base_url.rstrip("/")
        self.reconnects = 0

    def stream_url(self, symbols: list[str]) -> str:
        streams = "/".join(f"{symbol.lower()}@miniTicker" for symbol in symbols)
        return f"{self.base_url}?streams={streams}"

    async def iter_tickers(self, symbols: list[str]):
        normalized = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
        if not normalized:
            return
        reconnect_delay = 1.0
        while True:
            try:
                async with websockets.connect(
                    self.stream_url(normalized),
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2**20,
                ) as socket:
                    reconnect_delay = 1.0
                    async for raw_message in socket:
                        payload = json.loads(raw_message)
                        data = payload.get("data", payload) if isinstance(payload, dict) else {}
                        symbol = str(data.get("s", "")).upper()
                        raw_price = data.get("c") or data.get("p")
                        if symbol in normalized and raw_price is not None:
                            yield Ticker(symbol, float(raw_price))
            except asyncio.CancelledError:
                raise
            except RuntimeError as exc:
                if "no running event loop" in str(exc).lower():
                    return
                self.reconnects += 1
                try:
                    await asyncio.sleep(reconnect_delay)
                except RuntimeError:
                    return
                reconnect_delay = min(reconnect_delay * 2, 30.0)
            except Exception:
                self.reconnects += 1
                try:
                    await asyncio.sleep(reconnect_delay)
                except RuntimeError:
                    return
                reconnect_delay = min(reconnect_delay * 2, 30.0)
