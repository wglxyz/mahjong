"""A meld is a grouped set of tiles displayed in front of a player (副露).

We model it as an Entity that contains other tiles, so it sits cleanly in the player's
`melds` Zone alongside other Meld entities. The contained tiles are NOT also in any
ordinary tile zone — the meld owns them.
"""
from __future__ import annotations

from core.entity import Entity
from core.player import PlayerId
from mahjong.tile import Tile

CHI = "chi"            # sequence, always called from previous-seat discard
PON = "pon"            # triplet, called from any opponent
MINKAN = "minkan"      # open quad, called from any opponent
ANKAN = "ankan"        # closed quad, declared from own hand
SHOUMINKAN = "shouminkan"  # added kan: upgrading an existing pon by adding a 4th tile from draw

MELD_TYPES = (CHI, PON, MINKAN, ANKAN, SHOUMINKAN)


class Meld(Entity):
    __slots__ = ("meld_type", "tiles", "called_from", "called_tile_id")

    def __init__(
        self,
        meld_type: str,
        tiles: tuple[Tile, ...],
        called_from: PlayerId | None = None,
        called_tile_id: int | None = None,
    ) -> None:
        super().__init__()
        if meld_type not in MELD_TYPES:
            raise ValueError(f"unknown meld type: {meld_type}")
        self.meld_type = meld_type
        self.tiles = tiles
        self.called_from = called_from        # seat of player whose discard formed the meld
        self.called_tile_id = called_tile_id  # entity id of that discarded tile

    @property
    def is_concealed(self) -> bool:
        return self.meld_type == ANKAN

    def __repr__(self) -> str:
        body = " ".join(repr(t) for t in self.tiles)
        return f"<{self.meld_type} {body}>"
