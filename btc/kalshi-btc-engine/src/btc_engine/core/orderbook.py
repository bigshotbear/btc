from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

Side = Literal["bid", "ask"]


@dataclass(slots=True)
class L2Book:
    bids: dict[Decimal, Decimal] = field(default_factory=dict)
    asks: dict[Decimal, Decimal] = field(default_factory=dict)

    def clear(self) -> None:
        self.bids.clear()
        self.asks.clear()

    def set_level(self, side: Side, price: Decimal, quantity: Decimal) -> None:
        levels = self.bids if side == "bid" else self.asks
        if quantity <= 0:
            levels.pop(price, None)
        else:
            levels[price] = quantity
        self._assert_valid()

    def replace(self, bids: list[tuple[Decimal, Decimal]], asks: list[tuple[Decimal, Decimal]]) -> None:
        self.bids = {p: q for p, q in bids if q > 0}
        self.asks = {p: q for p, q in asks if q > 0}
        self._assert_valid()

    @property
    def best_bid(self) -> tuple[Decimal, Decimal] | None:
        if not self.bids:
            return None
        price = max(self.bids)
        return price, self.bids[price]

    @property
    def best_ask(self) -> tuple[Decimal, Decimal] | None:
        if not self.asks:
            return None
        price = min(self.asks)
        return price, self.asks[price]

    def depth_weighted_price(self, side: Literal["buy", "sell"], quantity: Decimal) -> Decimal | None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        levels = self.asks if side == "buy" else self.bids
        ordered = sorted(levels.items(), reverse=side == "sell")
        remaining = quantity
        cost = Decimal("0")
        for price, available in ordered:
            take = min(remaining, available)
            cost += price * take
            remaining -= take
            if remaining <= 0:
                return cost / quantity
        return None

    def _assert_valid(self) -> None:
        if any(p <= 0 or q <= 0 for p, q in self.bids.items()):
            raise ValueError("invalid bid level")
        if any(p <= 0 or q <= 0 for p, q in self.asks.items()):
            raise ValueError("invalid ask level")
        if self.bids and self.asks and max(self.bids) >= min(self.asks):
            raise ValueError("crossed order book")


def kalshi_unified_level_to_executable_side(
    book_side: str, yes_price: Decimal
) -> tuple[Literal["bid", "ask"], Decimal]:
    """Normalize Kalshi unified yes-price book levels into a YES contract book.

    With use_yes_price=true, YES-side levels are YES bids and NO-side levels are
    equivalent YES asks at the same unified price scale.
    """
    if not Decimal("0") <= yes_price <= Decimal("1"):
        raise ValueError("Kalshi probability price outside [0, 1]")
    if book_side == "yes":
        return "bid", yes_price
    if book_side == "no":
        return "ask", yes_price
    raise ValueError(f"unknown Kalshi book side: {book_side}")
