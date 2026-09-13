"""Spot execution adapter with an explicit mode gate and no automatic retries."""

from dataclasses import dataclass, field
from decimal import Decimal
from urllib.error import HTTPError

from .binance import BinancePrivateClient
from .core import OrderStatus, PaperOrder, RiskDecision, TradeIntent
from .filters import SymbolFilters


@dataclass
class BinanceSpotBroker:
    """Map the central order boundary to Binance Spot Testnet or guarded LIVE.

    The adapter never retries an ambiguous submission. A failed query or
    transport error is returned as UNKNOWN so reconciliation can inspect the
    exchange before another action is considered.
    """

    client: BinancePrivateClient
    trading_mode: str
    live_trading_enabled: bool = False
    filters: dict[str, SymbolFilters] = field(default_factory=dict)
    orders: dict[str, PaperOrder] = field(default_factory=dict)

    @property
    def can_submit(self) -> bool:
        if self.trading_mode == "testnet":
            return "testnet.binance" in self.client.base_url
        return self.trading_mode == "live" and self.live_trading_enabled

    def submit(self, intent: TradeIntent, decision: RiskDecision) -> PaperOrder:
        existing = self.orders.get(intent.idempotency_key)
        if existing is not None:
            return existing
        if not decision.approved:
            order = PaperOrder(intent.idempotency_key, intent, OrderStatus.REJECTED)
            self.orders[intent.idempotency_key] = order
            return order
        if not self.can_submit:
            order = PaperOrder(intent.idempotency_key, intent, OrderStatus.REJECTED)
            self.orders[intent.idempotency_key] = order
            return order
        symbol_filter = self.filters.get(intent.symbol.upper())
        if symbol_filter is None:
            order = PaperOrder(intent.idempotency_key, intent, OrderStatus.REJECTED)
            self.orders[intent.idempotency_key] = order
            return order
        valid, _ = symbol_filter.validate(
            price=Decimal(str(intent.price)), quantity=Decimal(str(intent.quantity))
        )
        if not valid:
            order = PaperOrder(intent.idempotency_key, intent, OrderStatus.REJECTED)
            self.orders[intent.idempotency_key] = order
            return order
        price = symbol_filter.normalize_price(Decimal(str(intent.price)))
        quantity = symbol_filter.normalize_quantity(Decimal(str(intent.quantity)))
        price_text = format(price, "f")
        quantity_text = format(quantity, "f")
        try:
            client_order_id = self._client_order_id(intent)
            remote = self.client.query_spot_order(
                symbol=intent.symbol, client_order_id=client_order_id
            )
            order = self._map_remote_order(intent, remote)
            order.client_order_id = client_order_id
            self.orders[intent.idempotency_key] = order
            return order
        except HTTPError as exc:
            if exc.code not in {400, 404}:
                order = PaperOrder(intent.idempotency_key, intent, OrderStatus.UNKNOWN)
                self.orders[intent.idempotency_key] = order
                return order
        except Exception:
            order = PaperOrder(intent.idempotency_key, intent, OrderStatus.UNKNOWN)
            self.orders[intent.idempotency_key] = order
            return order
        try:
            remote = self.client.place_spot_limit_order(
                symbol=intent.symbol,
                side=intent.side.value,
                quantity=quantity_text,
                price=price_text,
                client_order_id=client_order_id,
            )
        except HTTPError:
            order = PaperOrder(intent.idempotency_key, intent, OrderStatus.UNKNOWN)
            self.orders[intent.idempotency_key] = order
            return order
        except Exception:
            order = PaperOrder(intent.idempotency_key, intent, OrderStatus.UNKNOWN)
            self.orders[intent.idempotency_key] = order
            return order
        order = self._map_remote_order(intent, remote)
        order.client_order_id = client_order_id
        self.orders[intent.idempotency_key] = order
        return order

    def cancel_pending(self) -> int:
        canceled = 0
        managed_prefix = "AD-T-" if self.trading_mode == "testnet" else "AD-L-"
        try:
            remote_orders = self.client.open_orders()
        except Exception:
            return 0
        for remote in remote_orders:
            if str(remote.get("status", "")).upper() not in {"NEW", "PARTIALLY_FILLED"}:
                continue
            symbol = str(remote.get("symbol", ""))
            order_id = str(remote.get("orderId")) if remote.get("orderId") is not None else None
            client_id = (
                str(remote.get("clientOrderId"))
                if remote.get("clientOrderId") is not None
                else None
            )
            # A hard stop belongs to AlgoDesk-managed orders only; never cancel
            # unrelated manual orders on the same Binance account.
            if client_id is None or not client_id.startswith(managed_prefix):
                continue
            try:
                self.client.cancel_spot_order(
                    symbol=symbol, order_id=order_id, client_order_id=client_id
                )
                canceled += 1
            except Exception:
                # Cancellation is deliberately best effort; reconciliation owns recovery.
                continue
        return canceled

    @staticmethod
    def _map_remote_order(intent: TradeIntent, remote: dict[str, object]) -> PaperOrder:
        raw_status = str(remote.get("status", "UNKNOWN")).upper()
        status_map = {
            "NEW": OrderStatus.SUBMITTED,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.CANCELED,
        }
        status = status_map.get(raw_status, OrderStatus.UNKNOWN)
        filled_quantity = float(str(remote.get("executedQty", 0) or 0))
        return PaperOrder(
            client_order_id=intent.idempotency_key,
            intent=intent,
            status=status,
            filled_quantity=filled_quantity,
            raw_response=remote,
        )

    def _client_order_id(self, intent: TradeIntent) -> str:
        prefix = "T" if self.trading_mode == "testnet" else "L"
        return f"AD-{prefix}-{intent.idempotency_key}"[:36]
