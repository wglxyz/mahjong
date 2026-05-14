"""Run AbstractMahjongGame + SimpleRuleset with random AIs and print the event log."""
from __future__ import annotations
import random as _random
import sys

from core.action import Action
from core.engine import Engine
from core.event import Event
from core.event_bus import EventBus
from core.player import PlayerId
from core.rng import RNG
from core.state import GameState
from mahjong.abstract_game import AbstractMahjongGame
from mahjong.events import (
    HandDrawn,
    HandWon,
    MeldFormed,
    TileDiscarded,
    TileDrawn,
)
from rules.simple import SimpleRuleset


class RandomProvider:
    """Uniform-random action picker. Good enough to verify the engine doesn't deadlock."""

    def __init__(self, seed: int) -> None:
        self._r = _random.Random(seed)

    def choose(self, state: GameState, me: PlayerId, legal: list[Action]) -> Action:
        return self._r.choice(legal)


class WinSeekingProvider:
    """Slight bias so games actually end in a win sometimes: always declare win when offered,
    always pon (helps build hands), otherwise random. Prevents the random walk from converging
    to drawn games."""

    def __init__(self, seed: int) -> None:
        self._r = _random.Random(seed)

    def choose(self, state: GameState, me: PlayerId, legal: list[Action]) -> Action:
        from mahjong.actions import DeclareWinAction, PonAction
        for a in legal:
            if isinstance(a, DeclareWinAction):
                return a
        for a in legal:
            if isinstance(a, PonAction):
                return a
        return self._r.choice(legal)


def run(seed: int = 42, verbose: bool = True) -> tuple[list[PlayerId], str]:
    names = ["E", "S", "W", "N"]
    ruleset = SimpleRuleset()
    game = AbstractMahjongGame(ruleset, player_names=names)
    state = GameState(rng=RNG(seed=seed))
    providers = {i: WinSeekingProvider(seed=seed * 7 + i) for i in range(4)}
    bus = EventBus()

    def label(seat: PlayerId) -> str:
        return names[seat]

    def find_tile(tid: int):
        # search all zones
        for z in state.zones.values():
            for t in z.items:
                if t.id == tid:
                    return t
        for p in state.players.values():
            for z in p.zones.values():
                for t in z.items:
                    if hasattr(t, "id") and t.id == tid:
                        return t
        return None

    result_kind = {"value": "running"}

    def log(e: Event) -> None:
        if not verbose:
            if isinstance(e, HandWon):
                result_kind["value"] = "win"
            elif isinstance(e, HandDrawn):
                result_kind["value"] = "drawn"
            return
        if isinstance(e, TileDrawn):
            t = find_tile(e.tile_id)
            tag = " (rinshan)" if e.from_dead_wall else ""
            print(f"  {label(e.seat)} draws {t}{tag}")
        elif isinstance(e, TileDiscarded):
            t = find_tile(e.tile_id)
            tag = " *RIICHI*" if e.riichi else ""
            print(f"  {label(e.seat)} discards {t}{tag}")
        elif isinstance(e, MeldFormed):
            from_seat = "" if e.called_from is None else f" from {label(e.called_from)}"
            print(f"  {label(e.seat)} forms {e.meld_type}{from_seat}")
        elif isinstance(e, HandWon):
            kind = "tsumo" if e.loser is None else f"ron from {label(e.loser)}"
            print(f"\n>>> {label(e.winner)} wins by {kind} (+{e.score})")
            result_kind["value"] = "win"
        elif isinstance(e, HandDrawn):
            print("\n>>> drawn game (流局)")
            result_kind["value"] = "drawn"

    bus.subscribe(log)
    engine = Engine(game, state, providers, bus, max_steps=20_000)
    winners = engine.run()

    if verbose:
        print("\nFinal points:")
        for s in range(4):
            print(f"  {label(s)}: {state.players[s].resources['points'].value}")

    return winners, result_kind["value"]


def main() -> int:
    winners, kind = run(seed=42, verbose=True)
    print(f"\nresult: {kind}, winners={winners}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
