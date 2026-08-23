from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


class BudgetExceeded(RuntimeError):
    def __init__(self, budget: str):
        super().__init__(f"browser budget exhausted: {budget}")
        self.budget = budget


@dataclass(slots=True)
class BudgetLedger:
    limits: dict[str, int]
    deadline: float
    used: dict[str, int] = field(default_factory=dict)

    @classmethod
    def start(cls, limits: dict[str, int], elapsed_seconds: int) -> "BudgetLedger":
        return cls(dict(limits), monotonic() + elapsed_seconds)

    def check_time(self) -> None:
        if monotonic() >= self.deadline:
            raise BudgetExceeded("elapsed_seconds")

    def consume(self, key: str, amount: int = 1) -> None:
        self.check_time()
        if key not in self.limits:
            raise BudgetExceeded(key)
        next_value = self.used.get(key, 0) + amount
        if next_value > self.limits[key]:
            raise BudgetExceeded(key)
        self.used[key] = next_value

    def remaining_seconds(self) -> float:
        return max(0.0, self.deadline - monotonic())
