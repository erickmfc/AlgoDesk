"""Binance Spot adapters for public market data and guarded account access."""

import asyncio
import hashlib
import hmac
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import websockets

from .strategies import Candle


@dataclass(frozen=True)
class Ticker:
    symbol: str
    price: float


class BinancePublicClient:
    def __init__(self, base_url: str = "https://api.binance.com") -> None:
        self.base_url = base_url.rstrip("/")

    def ticker_price(self, symbols: list[str]) -> list[Ticker]:
        query = urlencode(
            {"symbols": json.dumps([symbol.upper() for symbol in symbols], separators=(",", ":"))}
        )
        request = Request(
            f"{self.base_url}/api/v3/ticker/price?{query}", headers={"User-Agent": "AlgoDesk/0.1"}
        )
        with urlopen(request, timeout=8) as response:  # noqa: S310 - fixed Binance HTTPS endpoint
            payload = json.load(response)
        if isinstance(payload, dict):
            payload = [payload]
        return [Ticker(str(row["symbol"]), float(row["price"])) for row in payload]

    def exchange_info(self, symbol: str) -> dict[str, object]:
        query = urlencode({"symbol": symbol.upper()})
        request = Request(
            f"{self.base_url}/api/v3/exchangeInfo?{query}", headers={"User-Agent": "AlgoDesk/0.1"}
        )
        with urlopen(request, timeout=8) as response:  # noqa: S310 - fixed Binance HTTPS endpoint
            return json.load(response)

    def klines(self, symbol: str, interval: str = "1h", limit: int = 500) -> list[Candle]:
        bounded_limit = min(max(int(limit), 1), 1000)
        query = urlencode({"symbol": symbol.upper(), "interval": interval, "limit": bounded_limit})
        request = Request(
            f"{self.base_url}/api/v3/klines?{query}", headers={"User-Agent": "AlgoDesk/0.1"}
        )
        with urlopen(request, timeout=12) as response:  # noqa: S310 - fixed Binance HTTPS endpoint
            payload = json.load(response)
        if not isinstance(payload, list):
            raise ValueError("unexpected Binance klines response")
        candles: list[Candle] = []
        for row in payload:
            if not isinstance(row, list) or len(row) < 7:
                continue
            candles.append(
                Candle(
                    int(row[0]),
                    float(row[1]),
                    float(row[2]),
                    float(row[3]),
                    float(row[4]),
                    float(row[5]),
                )
            )
        if not candles:
            raise ValueError("Binance returned no klines")
        return candles


class BinancePrivateClient(BinancePublicClient):
    """Signed account and low-level Spot order endpoint adapter."""

    def __init__(
        self, api_key: str, api_secret: str, base_url: str = "https://api.binance.com"
    ) -> None:
        super().__init__(base_url)
        self.api_key = api_key.strip()
        self.api_secret = api_secret

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def account_information(self) -> dict[str, object]:
        payload = self._signed_request("GET", "/api/v3/account", {"omitZeroBalances": "true"})
        if not isinstance(payload, dict):
            raise ValueError("unexpected Binance account response")
        return payload

    def open_orders(self, symbol: str | None = None) -> list[dict[str, object]]:
        params = {"symbol": symbol.upper()} if symbol else {}
        payload = self._signed_request("GET", "/api/v3/openOrders", params)
        if not isinstance(payload, list):
            raise ValueError("unexpected Binance open orders response")
        return [row for row in payload if isinstance(row, dict)]

    def my_trades(self, symbol: str, limit: int = 100) -> list[dict[str, object]]:
        payload = self._signed_request(
            "GET", "/api/v3/myTrades", {"symbol": symbol.upper(), "limit": min(max(limit, 1), 1000)}
        )
        if not isinstance(payload, list):
            raise ValueError("unexpected Binance trades response")
        return [row for row in payload if isinstance(row, dict)]

    def place_spot_limit_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: str,
        price: str,
        client_order_id: str,
    ) -> dict[str, object]:
        """Submit one LIMIT order; callers must enforce the mode safety gate."""
        payload = self._signed_request(
            "POST",
            "/api/v3/order",
            {
                "symbol": symbol.upper(),
                "side": side.upper(),
                "type": "LIMIT",
                "timeInForce": "GTC",
                "quantity": quantity,
                "price": price,
                "newClientOrderId": client_order_id,
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("unexpected Binance order response")
        return payload

    def cancel_spot_order(
        self, *, symbol: str, order_id: str | None = None, client_order_id: str | None = None
    ) -> dict[str, object]:
        if not order_id and not client_order_id:
            raise ValueError("order_id or client_order_id is required")
        params: dict[str, object] = {"symbol": symbol.upper()}
        if order_id:
            params["orderId"] = order_id
        else:
            params["origClientOrderId"] = client_order_id
        payload = self._signed_request("DELETE", "/api/v3/order", params)
        if not isinstance(payload, dict):
            raise ValueError("unexpected Binance cancel response")
        return payload

    def query_spot_order(
        self, *, symbol: str, order_id: str | None = None, client_order_id: str | None = None
    ) -> dict[str, object]:
        if not order_id and not client_order_id:
            raise ValueError("order_id or client_order_id is required")
        params: dict[str, object] = {"symbol": symbol.upper()}
        if order_id:
            params["orderId"] = order_id
        else:
            params["origClientOrderId"] = client_order_id
        payload = self._signed_request("GET", "/api/v3/order", params)
        if not isinstance(payload, dict):
            raise ValueError("unexpected Binance order query response")
        return payload

    def create_user_data_stream(self) -> str:
        payload = self._api_key_request("POST", "/api/v3/userDataStream")
        listen_key = payload.get("listenKey") if isinstance(payload, dict) else None
        if not isinstance(listen_key, str) or not listen_key:
            raise ValueError("Binance did not return a listen key")
        return listen_key

    def keepalive_user_data_stream(self, listen_key: str) -> None:
        self._api_key_request("PUT", "/api/v3/userDataStream", {"listenKey": listen_key})

    def _signed_request(self, method: str, path: str, params: Mapping[str, object]) -> object:
        if not self.configured:
            raise RuntimeError("Binance account credentials are not configured")
        signed_params = {**params, "recvWindow": "5000", "timestamp": str(int(time.time() * 1000))}
        query = urlencode(signed_params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        request = Request(
            f"{self.base_url}{path}?{query}&signature={signature}",
            headers={"User-Agent": "AlgoDesk/0.1", "X-MBX-APIKEY": self.api_key},
            method=method,
        )
        with urlopen(request, timeout=8) as response:  # noqa: S310 - fixed Binance HTTPS endpoint
            return json.load(response)

    def _api_key_request(
        self, method: str, path: str, params: Mapping[str, object] | None = None
    ) -> object:
        if not self.api_key:
            raise RuntimeError("Binance API key is not configured")
        query = urlencode(params or {})
        suffix = f"?{query}" if query else ""
        request = Request(
            f"{self.base_url}{path}{suffix}",
            headers={"User-Agent": "AlgoDesk/0.1", "X-MBX-APIKEY": self.api_key},
            method=method,
        )
        with urlopen(request, timeout=8) as response:  # noqa: S310 - fixed Binance HTTPS endpoint
            return json.load(response)


class BinanceUserDataStream:
    """Authenticated account-event stream; it never submits trading commands."""

    def __init__(self, base_url: str = "wss://stream.binance.com:9443/ws") -> None:
        self.base_url = base_url.rstrip("/")
        self.reconnects = 0
        self.connected = False
        self.last_message_at: float | None = None

    def stream_url(self, listen_key: str) -> str:
        return f"{self.base_url}/{listen_key}"

    async def iter_events(self, listen_key: str, on_reconnect=None):
        reconnect_delay = 1.0
        while True:
            try:
                async with websockets.connect(
                    self.stream_url(listen_key),
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2**20,
                ) as socket:
                    self.connected = True
                    reconnect_delay = 1.0
                    async for raw_message in socket:
                        payload = json.loads(raw_message)
                        if isinstance(payload, dict):
                            self.last_message_at = time.time()
                            yield payload
            except asyncio.CancelledError:
                raise
            except Exception:
                self.connected = False
                self.reconnects += 1
                if on_reconnect is not None:
                    await on_reconnect()
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 30.0)


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
