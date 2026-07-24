from __future__ import annotations

from dataclasses import dataclass, field


class SequenceGap(RuntimeError):
    pass


@dataclass(slots=True)
class SequenceTracker:
    """Tracks monotonically increasing sequence IDs per logical stream."""

    last: dict[str, int] = field(default_factory=dict)

    def observe(self, stream: str, sequence: int | None, *, strict_increment: bool = True) -> None:
        if sequence is None:
            return
        previous = self.last.get(stream)
        if previous is None:
            self.last[stream] = sequence
            return
        if sequence <= previous:
            # Duplicate or out-of-order frames are ignored but not allowed to rewind state.
            return
        if strict_increment and sequence != previous + 1:
            raise SequenceGap(f"{stream}: expected {previous + 1}, got {sequence}")
        self.last[stream] = sequence

    def reset(self, stream: str | None = None) -> None:
        if stream is None:
            self.last.clear()
        else:
            self.last.pop(stream, None)
