from __future__ import annotations
from dataclasses import dataclass, field

from core.player import Player, PlayerId
from core.zone import Zone
from core.rng import RNG


@dataclass
class GameState:
    """The whole mutable world. Engine and GameDef mutate this in-place."""
    players: dict[PlayerId, Player] = field(default_factory=dict)
    zones: dict[str, Zone] = field(default_factory=dict)   # shared zones (deck, board, ...)
    rng: RNG = field(default_factory=lambda: RNG(0))
    phase: str = "setup"
    turn: int = 0
    attrs: dict[str, object] = field(default_factory=dict)  # game-specific scratch

    def player_order(self) -> list[PlayerId]:
        return sorted(self.players.keys())
