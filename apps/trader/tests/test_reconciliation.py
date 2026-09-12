from src.binance import BinancePrivateClient
from src.reconciliation import AccountReconciler


def test_reconciliation_marks_matching_state_synced(monkeypatch):
    client = BinancePrivateClient("key", "secret")
    monkeypatch.setattr(
        client,
        "account_information",
        lambda: {"balances": [{"asset": "USDT", "free": "100", "locked": "0"}]},
    )
    monkeypatch.setattr(client, "open_orders", lambda: [{"orderId": 17}])

    result = AccountReconciler().reconcile(
        client,
        local_balances={"USDT": 100.0},
        local_open_order_ids={"17"},
    )

    assert result.status == "SYNCED"
    assert result.remote_open_orders == 1


def test_reconciliation_marks_divergence_without_resubmit(monkeypatch):
    client = BinancePrivateClient("key", "secret")
    monkeypatch.setattr(
        client,
        "account_information",
        lambda: {"balances": [{"asset": "USDT", "free": "80", "locked": "0"}]},
    )
    monkeypatch.setattr(client, "open_orders", lambda: [{"orderId": 18}])

    result = AccountReconciler().reconcile(
        client,
        local_balances={"USDT": 100.0},
        local_open_order_ids={"17"},
    )

    assert result.status == "DIVERGED"
    assert result.missing_local_orders == ("17",)
    assert result.unknown_remote_orders == ("18",)
