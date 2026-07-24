from __future__ import annotations

from decimal import Decimal

QUARTER_MS = 15 * 60 * 1000
MINUTE_MS = 60 * 1000


def next_quarter_close_ms(source_timestamp_ms: int) -> int:
    remainder = source_timestamp_ms % QUARTER_MS
    if remainder == 0:
        return source_timestamp_ms
    return source_timestamp_ms + (QUARTER_MS - remainder)


def in_quarter_final_minute(source_timestamp_ms: int) -> bool:
    close_ms = next_quarter_close_ms(source_timestamp_ms)
    return close_ms - MINUTE_MS < source_timestamp_ms <= close_ms


def settles_up_from_cent_observations(observation_cents: list[int], target: Decimal) -> bool:
    """Exact strict-above comparison without floating-point arithmetic.

    The caller must first verify that strict-above is the live contract rule.
    """
    if len(observation_cents) != 60:
        raise ValueError("exact settlement comparison requires 60 observations")
    target_cents = int((target * 100).to_integral_exact())
    return sum(observation_cents) > 60 * target_cents
