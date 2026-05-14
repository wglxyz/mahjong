"""Standard mahjong actions. Rulesets decide which are actually offered at each decision point.

Tile ids reference Entity ids — that way an action can survive across shuffles and the
ruleset/engine resolves them through the current zones.
"""
from __future__ import annotations
from dataclasses import dataclass

from core.action import Action


@dataclass(frozen=True)
class DiscardAction(Action):
    tile_id: int


@dataclass(frozen=True)
class PassAction(Action):
    """Decline to act in a response window."""
    pass


@dataclass(frozen=True)
class ChiAction(Action):
    """Form a sequence with the just-discarded tile + two tiles from hand."""
    hand_tile_ids: tuple[int, int]


@dataclass(frozen=True)
class PonAction(Action):
    """Form a triplet with the discard + two matching tiles from hand."""
    hand_tile_ids: tuple[int, int]


@dataclass(frozen=True)
class KanAction(Action):
    """Form a quad. `kind` is one of 'minkan' | 'ankan' | 'shouminkan'.

    minkan: 3 ids from hand + the discarded tile (claimed from response window)
    ankan:  4 ids from hand, declared during own AFTER_DRAW
    shouminkan: 1 id (the 4th tile, drawn this turn) added to an existing pon
    """
    kind: str
    hand_tile_ids: tuple[int, ...]


@dataclass(frozen=True)
class DeclareWinAction(Action):
    """Tsumo (self-drawn) when offered in AFTER_DRAW, or Ron when offered in RESPONSE."""
    kind: str  # "tsumo" | "ron"


@dataclass(frozen=True)
class DeclareRiichiAction(Action):
    """Reach declaration (riichi only). Carries the tile to discard alongside the declaration."""
    discard_tile_id: int
