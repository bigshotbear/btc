from decimal import Decimal

import pytest

from btc_engine.core.settlement import in_quarter_final_minute, settles_up_from_cent_observations


def test_final_minute_boundaries() -> None:
    quarter_close = 15 * 60 * 1000
    assert not in_quarter_final_minute(quarter_close - 60_000)
    assert in_quarter_final_minute(quarter_close - 59_000)
    assert in_quarter_final_minute(quarter_close)


def test_exact_strict_above() -> None:
    observations = [10000] * 60
    assert not settles_up_from_cent_observations(observations, Decimal("100.00"))
    observations[-1] = 10001
    assert settles_up_from_cent_observations(observations, Decimal("100.00"))
    with pytest.raises(ValueError):
        settles_up_from_cent_observations([10000], Decimal("100.00"))
