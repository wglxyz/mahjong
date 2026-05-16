from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.action import Action
from core.event import Event
from core.player import PlayerId
from core.state import GameState


@dataclass
class DecisionPoint:
    """What the engine needs from one or more players right now.

    Multiple players can appear simultaneously to model response windows
    (mahjong: after a discard, several seats may claim chi/pon/kan/ron).
    The GameDef's `apply` resolves priority among the collected decisions.
    """
    legal_actions: dict[PlayerId, list[Action]]


@runtime_checkable
class GameDef(Protocol):
    """Contract every concrete game implements. Engine talks only to this."""

    def setup(self, state: GameState) -> list[Event]:
        """Initialise zones, players, deal opening tiles, etc. Return any events to broadcast
        before the first decision point (e.g. HandStarted, initial draws)."""

    def decision_point(self, state: GameState) -> DecisionPoint | None: ...

    def apply(self, state: GameState, decisions: dict[PlayerId, Action]) -> list[Event]: ...

    def is_terminal(self, state: GameState) -> bool: ...

    def winners(self, state: GameState) -> list[PlayerId]: ...
