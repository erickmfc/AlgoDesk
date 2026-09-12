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
        remote_order_ids = {str(row["orderId"]) for row in remote_orders if "orderId" in row}
        missing_local = tuple(sorted(local_open_order_ids - remote_order_ids))
        unknown_remote = tuple(sorted(remote_order_ids - local_open_order_ids))
        status = (
            "SYNCED"
            if not balance_mismatches and not missing_local and not unknown_remote
            else "DIVERGED"
        )
        return ReconciliationResult(
            status,
            balance_mismatches,
            missing_local,
            unknown_remote,
            len(remote_orders),
        )
