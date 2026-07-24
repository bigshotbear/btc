from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ReceiveStamp:
    wall_time: datetime
    monotonic_ns: int

    @classmethod
    def now(cls) -> "ReceiveStamp":
        return cls(wall_time=utc_now(), monotonic_ns=time.monotonic_ns())
