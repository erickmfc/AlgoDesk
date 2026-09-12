from src.models import Base


def test_required_persistence_tables_exist():
    required = {"candles", "strategies", "trade_intents", "orders", "fills", "portfolio_snapshots", "risk_events", "system_events", "bot_status"}
    assert required.issubset(Base.metadata.tables)


def test_candle_key_prevents_duplicate_market_data():
    constraints = Base.metadata.tables["candles"].constraints
    assert any(getattr(constraint, "columns", None) and {column.name for column in constraint.columns} == {"exchange", "symbol", "interval", "open_time"} for constraint in constraints)
