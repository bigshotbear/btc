from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Hypothesis:
    hypothesis_id: str
    feature_name: str
    rationale: str
    decision_criterion: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


INITIAL_HYPOTHESES = [
    Hypothesis(
        "H001",
        "ofi_x_inverse_depth",
        "Aggressive order flow should move price more when opposing depth is thin.",
        "Keep only if interaction improves day-block OOS net EV and calibration across 3 folds.",
    ),
    Hypothesis(
        "H002",
        "microprice_x_queue_imbalance",
        "Microprice displacement and queue imbalance may jointly predict the next spot move.",
        "Keep only if joint model beats each feature alone out of sample.",
    ),
    Hypothesis(
        "H003",
        "flow_persistence_x_failed_refill",
        "Persistent taker flow with weak opposing refill may contain unincorporated pressure.",
        "Keep only if receive-time signal survives measured Kalshi execution latency.",
    ),
]
