"""Read-only account reconciliation primitives for the Testnet gate."""

from dataclasses import dataclass

from .binance import BinancePrivateClient


@dataclass(frozen=True)
class ReconciliationResult:
    status: str
    balance_mismatches: tuple[str, ...]
    missing_local_orders: tuple[str, ...]
    unknown_remote_orders: tuple[str, ...]
    remote_open_orders: int
    missing_local_fills: tuple[str, ...] = ()
    unknown_remote_fills: tuple[str, ...] = ()
    remote_orders: int = 0
    remote_fills: int = 0


class AccountReconciler:
    """Compare local expectations with Binance, without retrying orders."""

    def __init__(self, tolerance: float = 1e-8) -> None:
        self.tolerance = tolerance

    def reconcile(
        self,
        client: BinancePrivateClient,
        *,
        local_balances: dict[str, float],
        local_open_order_ids: set[str],
        local_order_ids: set[str] | None = None,
        local_fill_order_ids: set[str] | None = None,
        symbol: str | None = None,
        managed_client_prefix: str | None = None,
    ) -> ReconciliationResult:
        if not client.configured:
            return ReconciliationResult("NOT_CONFIGURED", (), (), (), 0)
        account = client.account_information()
        raw_balances = account.get("balances", [])
        if not isinstance(raw_balances, list):
            raw_balances = []
        remote_balances = {
            str(row["asset"]): float(row.get("free", 0)) + float(row.get("locked", 0))
            for row in raw_balances
            if isinstance(row, dict) and "asset" in row
        }
        assets = set(local_balances) | set(remote_balances)
        balance_mismatches = tuple(
            f"{asset}: local={local_balances.get(asset, 0.0):.12g} remote={remote_balances.get(asset, 0.0):.12g}"
            for asset in sorted(assets)
            if abs(local_balances.get(asset, 0.0) - remote_balances.get(asset, 0.0))
            > self.tolerance
        )
        remote_orders = client.open_orders()
        remote_order_ids = {
            str(row.get("clientOrderId") or row.get("orderId"))
            for row in remote_orders
            if row.get("clientOrderId") is not None or row.get("orderId") is not None
        }
        missing_local = tuple(sorted(local_open_order_ids - remote_order_ids))
        unknown_remote = tuple(sorted(remote_order_ids - local_open_order_ids))
        missing_local_fills: tuple[str, ...] = ()
        unknown_remote_fills: tuple[str, ...] = ()
        remote_order_count = 0
        remote_fill_count = 0
        if symbol is not None:
            history_orders = client.all_orders(symbol)
            history_by_exchange_id: dict[str, str] = {}
            history_client_ids: set[str] = set()
            for row in history_orders:
                client_id = row.get("clientOrderId")
                if not isinstance(client_id, str):
                    continue
                if managed_client_prefix and not client_id.startswith(managed_client_prefix):
                    continue
                history_client_ids.add(client_id)
                if row.get("orderId") is not None:
                    history_by_exchange_id[str(row["orderId"])] = client_id
            remote_order_count = len(history_client_ids)
            known_local_order_ids = local_order_ids if local_order_ids is not None else set()
            if local_order_ids is not None:
                missing_history = known_local_order_ids - history_client_ids
                missing_local = tuple(sorted(set(missing_local) | missing_history))
                unknown_history = history_client_ids - known_local_order_ids
                unknown_remote = tuple(sorted(set(unknown_remote) | unknown_history))

            history_fills = client.my_trades(symbol, 1000)
            remote_fill_ids = {
                history_by_exchange_id[str(row["orderId"])]
                for row in history_fills
                if row.get("orderId") is not None and str(row["orderId"]) in history_by_exchange_id
            }
            remote_fill_count = len(remote_fill_ids)
            known_local_fill_ids = (
                local_fill_order_ids if local_fill_order_ids is not None else set()
            )
            if local_fill_order_ids is not None:
                missing_local_fills = tuple(sorted(known_local_fill_ids - remote_fill_ids))
                unknown_remote_fills = tuple(sorted(remote_fill_ids - known_local_fill_ids))
        status = (
            "SYNCED"
            if not balance_mismatches
            and not missing_local
            and not unknown_remote
            and not missing_local_fills
            and not unknown_remote_fills
            else "DIVERGED"
        )
        return ReconciliationResult(
            status,
            balance_mismatches,
            missing_local,
            unknown_remote,
            len(remote_orders),
            missing_local_fills,
            unknown_remote_fills,
            remote_order_count,
            remote_fill_count,
        )
