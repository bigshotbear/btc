from decimal import Decimal

from btc_engine.core.orderbook import L2Book, kalshi_unified_level_to_executable_side


def test_depth_weighted_price() -> None:
    book = L2Book()
    book.replace(
        bids=[(Decimal("0.55"), Decimal("10"))],
        asks=[(Decimal("0.56"), Decimal("5")), (Decimal("0.58"), Decimal("10"))],
    )
    assert book.depth_weighted_price("buy", Decimal("10")) == Decimal("0.57")


def test_kalshi_unified_book_mapping() -> None:
    assert kalshi_unified_level_to_executable_side("yes", Decimal("0.45")) == (
        "bid",
        Decimal("0.45"),
    )
    assert kalshi_unified_level_to_executable_side("no", Decimal("0.55")) == (
        "ask",
        Decimal("0.55"),
    )
