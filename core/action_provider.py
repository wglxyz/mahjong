from __future__ import annotations
from typing import Protocol, runtime_checkable

from core.action import Action
from core.player import PlayerId
from core.state import GameState


@runtime_checkable
class ActionProvider(Protocol):
    """Anything that can pick an Action for a player. UI adapters and AIs both implement this."""

    def choose(self, state: GameState, me: PlayerId, legal: list[Action]) -> Action: ...
