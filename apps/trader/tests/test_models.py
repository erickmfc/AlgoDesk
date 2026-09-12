from src.models import Base


def test_required_persistence_tables_exist():
    required = {"candles", "strategies", "strategy_runs", "signals", "trade_intents", "orders", "order_events", "fills", "portfolio_snapshots", "account_balances", "risk_events", "system_events", "bot_status"}
    assert required.issubset(Base.metadata.tables)


def test_candle_key_prevents_duplicate_market_data():
    constraints = Base.metadata.tables["candles"].constraints
    assert any(getattr(constraint, "columns", None) and {column.name for column in constraint.columns} == {"exchange", "symbol", "interval", "open_time"} for constraint in constraints)
