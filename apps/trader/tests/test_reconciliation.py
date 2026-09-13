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


def test_reconciliation_checks_managed_order_history_and_fills(monkeypatch):
    client = BinancePrivateClient("key", "secret")
    monkeypatch.setattr(
        client,
        "account_information",
        lambda: {"balances": [{"asset": "USDT", "free": "100", "locked": "0"}]},
    )
    monkeypatch.setattr(client, "open_orders", lambda: [])
    monkeypatch.setattr(
        client,
        "all_orders",
        lambda symbol: [
            {
                "orderId": 18,
                "clientOrderId": "AD-T-remote",
                "symbol": symbol,
                "status": "FILLED",
            }
        ],
    )
    monkeypatch.setattr(
        client,
        "my_trades",
        lambda symbol, limit: [{"orderId": 18, "symbol": symbol, "qty": "0.01"}],
    )

    result = AccountReconciler().reconcile(
        client,
        local_balances={"USDT": 100.0},
        local_open_order_ids=set(),
        local_order_ids=set(),
        local_fill_order_ids=set(),
        symbol="BTCUSDT",
        managed_client_prefix="AD-T-",
    )

    assert result.status == "DIVERGED"
    assert result.unknown_remote_orders == ("AD-T-remote",)
    assert result.unknown_remote_fills == ("AD-T-remote",)
    assert result.remote_orders == 1
    assert result.remote_fills == 1
