from __future__ import annotations
import random
from typing import Sequence, TypeVar, MutableSequence

T = TypeVar("T")


class RNG:
    """Seedable random source. Wrap stdlib random.Random so we can swap impls later (replay, fixed-seed tests)."""

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._r = random.Random(seed)

    def shuffle(self, seq: MutableSequence[T]) -> None:
        self._r.shuffle(seq)

    def randint(self, a: int, b: int) -> int:
        return self._r.randint(a, b)

    def choice(self, seq: Sequence[T]) -> T:
        return self._r.choice(seq)
