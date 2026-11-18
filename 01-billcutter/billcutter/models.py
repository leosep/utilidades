from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Charge:
    """A single expense. `amount` is always positive."""

    day: date
    description: str
    amount: float


@dataclass(frozen=True)
class Subscription:
    merchant: str
    frequency: str
    typical_amount: float
    monthly_cost: float
    charges: int
    last_charge: date
    next_charge: date
    cancel_url: str | None
