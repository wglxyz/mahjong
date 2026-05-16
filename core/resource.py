from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Resource:
    """A named numeric value with optional bounds. HP, mana, score, riichi sticks, etc."""
    name: str
    value: int = 0
    minimum: int | None = None
    maximum: int | None = None

    def adjust(self, delta: int) -> int:
        new = self.value + delta
        if self.minimum is not None:
            new = max(new, self.minimum)
        if self.maximum is not None:
            new = min(new, self.maximum)
        self.value = new
        return new

    def set(self, value: int) -> None:
        self.value = value
