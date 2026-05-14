"""Mahjong tile, specialised from core.Entity.

Suit codes (kept compact and ruleset-agnostic):
    m — manzu (萬子)         rank 1..9
    p — pinzu (筒子)         rank 1..9
    s — souzu (索子)         rank 1..9
    z — honors  (字牌)        rank 1..4 = winds E/S/W/N, 5..7 = dragons 白/發/中
    f — flowers/seasons      rank 1..8  (most rulesets ignore; included so we can model them)

A ruleset decides which of these suits it actually puts into the wall.
"""
from __future__ import annotations

from core.entity import Entity

SUIT_M = "m"
SUIT_P = "p"
SUIT_S = "s"
SUIT_Z = "z"
SUIT_F = "f"

NUMERIC_SUITS = (SUIT_M, SUIT_P, SUIT_S)
HONOR_SUIT = SUIT_Z
FLOWER_SUIT = SUIT_F

# pretty names for honors
HONOR_NAMES = {1: "E", 2: "S", 3: "W", 4: "N", 5: "白", 6: "發", 7: "中"}


class Tile(Entity):
    __slots__ = ("suit", "rank", "red")

    def __init__(self, suit: str, rank: int, red: bool = False) -> None:
        super().__init__()
        self.suit = suit
        self.rank = rank
        self.red = red

    @property
    def code(self) -> str:
        """Short string key, ignoring red. Two tiles with the same code are interchangeable for
        sequence/triplet purposes."""
        return f"{self.suit}{self.rank}"

    def __repr__(self) -> str:
        if self.suit == SUIT_Z:
            label = HONOR_NAMES.get(self.rank, f"z{self.rank}")
        else:
            label = f"{self.rank}{self.suit}"
        return f"0{label}" if self.red else label

    def is_numeric(self) -> bool:
        return self.suit in NUMERIC_SUITS

    def is_honor(self) -> bool:
        return self.suit == HONOR_SUIT

    def is_terminal_or_honor(self) -> bool:
        return self.suit == HONOR_SUIT or (self.is_numeric() and self.rank in (1, 9))
