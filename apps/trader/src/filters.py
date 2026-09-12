"""Runtime Binance symbol filters used before any future order submission."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


@dataclass(frozen=True)
class SymbolFilters:
    symbol: str
    min_price: Decimal = Decimal("0")
    max_price: Decimal = Decimal("0")
    tick_size: Decimal = Decimal("0")
    min_quantity: Decimal = Decimal("0")
    max_quantity: Decimal = Decimal("0")
    step_size: Decimal = Decimal("0")
    min_notional: Decimal = Decimal("0")

    @classmethod
    def from_exchange_info(cls, payload: dict[str, object]) -> "SymbolFilters":
        symbol = str(payload.get("symbol", "")).upper()
        values: dict[str, Decimal] = {}
        for item in payload.get("filters", []):
            if not isinstance(item, dict):
                continue
            filter_type = item.get("filterType")
            fields = {
                "PRICE_FILTER": ("minPrice", "min_price"),
                "LOT_SIZE": ("minQty", "min_quantity"),
            }
            if filter_type in fields:
                source, target = fields[filter_type]
                values[target] = Decimal(str(item.get(source, "0")))
                if filter_type == "PRICE_FILTER":
                    values["max_price"] = Decimal(str(item.get("maxPrice", "0")))
                    values["tick_size"] = Decimal(str(item.get("tickSize", "0")))
                else:
                    values["max_quantity"] = Decimal(str(item.get("maxQty", "0")))
                    values["step_size"] = Decimal(str(item.get("stepSize", "0")))
            elif filter_type in {"MIN_NOTIONAL", "NOTIONAL"}:
                values["min_notional"] = Decimal(str(item.get("minNotional", "0")))
        return cls(symbol=symbol, **values)

    def normalize_price(self, price: Decimal) -> Decimal:
        if self.tick_size <= 0:
            return price
        return (price / self.tick_size).to_integral_value(rounding=ROUND_DOWN) * self.tick_size

    def normalize_quantity(self, quantity: Decimal) -> Decimal:
        if self.step_size <= 0:
            return quantity
        return (quantity / self.step_size).to_integral_value(rounding=ROUND_DOWN) * self.step_size

    def validate(self, *, price: Decimal, quantity: Decimal) -> tuple[bool, str]:
        normalized_price = self.normalize_price(price)
        normalized_quantity = self.normalize_quantity(quantity)
        if normalized_price <= 0 or normalized_quantity <= 0:
            return False, "price and quantity must be positive after normalization"
        if self.min_price and normalized_price < self.min_price:
            return False, "price below PRICE_FILTER minimum"
        if self.max_price and normalized_price > self.max_price:
            return False, "price above PRICE_FILTER maximum"
        if self.min_quantity and normalized_quantity < self.min_quantity:
            return False, "quantity below LOT_SIZE minimum"
        if self.max_quantity and normalized_quantity > self.max_quantity:
            return False, "quantity above LOT_SIZE maximum"
        if self.min_notional and normalized_price * normalized_quantity < self.min_notional:
            return False, "order notional below Binance minimum"
        return True, "symbol filters passed"
