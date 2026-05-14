"""Mahjong events broadcast on the EventBus. UI subscribes here for rendering;
rulesets can also subscribe for triggered effects (e.g. ippatsu cancellation).
"""
from __future__ import annotations
from dataclasses import dataclass

from core.event import Event
from core.player import PlayerId


@dataclass(frozen=True)
class HandStarted(Event):
    dealer: PlayerId
    round_wind: int  # 1=E, 2=S, 3=W, 4=N
    hand_number: int


@dataclass(frozen=True)
class TileDrawn(Event):
    seat: PlayerId
    tile_id: int
    from_dead_wall: bool = False


@dataclass(frozen=True)
class TileDiscarded(Event):
    seat: PlayerId
    tile_id: int
    riichi: bool = False


@dataclass(frozen=True)
class MeldFormed(Event):
    seat: PlayerId
    meld_id: int
    meld_type: str
    called_from: PlayerId | None


@dataclass(frozen=True)
class RiichiDeclared(Event):
    seat: PlayerId


@dataclass(frozen=True)
class HandWon(Event):
    winner: PlayerId
    loser: PlayerId | None  # None for tsumo
    winning_tile_id: int
    score: int


@dataclass(frozen=True)
class HandDrawn(Event):
    """流局 — wall exhausted without a win."""
    tenpai_seats: tuple[PlayerId, ...] = ()
