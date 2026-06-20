"""Public contracts for hidden investor-committee debate."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_DEBATE_ROUNDS = 3
ATTITUDES = ("偏看多", "中性", "偏看空", "回避")


@dataclass(frozen=True)
class DebateConfig:
    rounds: int = DEFAULT_DEBATE_ROUNDS

    def __post_init__(self) -> None:
        if not 1 <= self.rounds <= 5:
            raise ValueError("debate rounds must be between 1 and 5")


@dataclass(frozen=True)
class DebateRound:
    round_number: int
    goal: str
    required_fields: tuple[str, ...] = ("attitude", "evidence", "risk")
