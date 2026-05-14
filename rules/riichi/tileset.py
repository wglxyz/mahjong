"""Build the 136-tile riichi wall.

  - m1..9, p1..9, s1..9: 4 copies each  (4 × 27 = 108)
  - z1..7 (East/South/West/North/白/發/中): 4 copies each  (4 × 7 = 28)
  - Optional red 5s: replace ONE copy of m5, p5, s5 with a red variant. Red counts as
    rank 5 for shape purposes but adds 1 dora-han per red present in the winning hand.
"""
from __future__ import annotations

from mahjong.tile import SUIT_M, SUIT_P, SUIT_S, SUIT_Z, Tile


def build_riichi_wall(red_fives: bool = True) -> list[Tile]:
    tiles: list[Tile] = []
    for suit in (SUIT_M, SUIT_P, SUIT_S):
        for rank in range(1, 10):
            for copy in range(4):
                is_red = red_fives and rank == 5 and copy == 0
                tiles.append(Tile(suit, rank, red=is_red))
    for rank in range(1, 8):
        for _ in range(4):
            tiles.append(Tile(SUIT_Z, rank))
    assert len(tiles) == 136
    return tiles


# next-tile mapping used for dora indicator → dora resolution.
# indicator → indicated:
#   numeric: rank wraps 1..9 → 2..9 then 1 (so indicator m9 means dora is m1)
#   winds:   E→S→W→N→E
#   dragons: 白→發→中→白
def dora_from_indicator(indicator: Tile) -> tuple[str, int]:
    """Return (suit, rank) of the actual dora given the visible indicator tile."""
    if indicator.suit == SUIT_Z:
        if 1 <= indicator.rank <= 4:
            return (SUIT_Z, indicator.rank % 4 + 1)         # E S W N → S W N E
        return (SUIT_Z, (indicator.rank - 5 + 1) % 3 + 5)   # 白發中 → 發中白
    next_rank = indicator.rank + 1 if indicator.rank < 9 else 1
    return (indicator.suit, next_rank)
