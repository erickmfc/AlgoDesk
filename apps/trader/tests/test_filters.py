from decimal import Decimal

from src.filters import SymbolFilters


def test_filters_normalize_and_validate_order():
    filters = SymbolFilters.from_exchange_info({
        "symbol": "BTCUSDT",
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000", "tickSize": "0.01"},
            {"filterType": "LOT_SIZE", "minQty": "0.0001", "maxQty": "100", "stepSize": "0.0001"},
            {"filterType": "MIN_NOTIONAL", "minNotional": "10"},
        ],
    })
    assert filters.normalize_price(Decimal("62340.109")) == Decimal("62340.10")
    assert filters.normalize_quantity(Decimal("0.012345")) == Decimal("0.0123")
    assert filters.validate(price=Decimal("62340.10"), quantity=Decimal("0.0123"))[0] is True
    assert filters.validate(price=Decimal("1"), quantity=Decimal("0.0001"))[0] is False
