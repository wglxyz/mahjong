"""Run a single hand of Riichi mahjong with 4 random AIs."""
from __future__ import annotations

import argparse
import random as _random
import sys
import time

from core.action import Action
from core.engine import Engine
from core.event import Event
from core.event_bus import EventBus
from core.player import PlayerId
from core.rng import RNG
from core.state import GameState
from mahjong.abstract_game import AbstractMahjongGame
from mahjong.actions import (
    ChiAction,
    DeclareRiichiAction,
    DeclareWinAction,
    KanAction,
    PonAction,
)
from mahjong.events import (
    HandDrawn,
    HandStarted,
    HandWon,
    MeldFormed,
    RiichiDeclared,
    TileDiscarded,
    TileDrawn,
)
from rules.riichi.ruleset import RiichiRuleset


class WinSeekingAI:
    """Take any win. Prefer calls + riichi to drive games to a conclusion. Tile-discard
    heuristic: drop honors and terminals first so the hand drifts toward tanyao shape."""

    def __init__(self, seed: int) -> None:
        self._r = _random.Random(seed)

    def choose(self, state: GameState, me: PlayerId, legal: list[Action]) -> Action:
        from mahjong.actions import DiscardAction
        from mahjong.tile import SUIT_Z
        # 1. always win
        for a in legal:
            if isinstance(a, DeclareWinAction):
                return a
        # 2. always riichi when offered (one option = first match)
        for a in legal:
            if isinstance(a, DeclareRiichiAction):
                return a
        # 3. take calls (chi/pon/kan) when offered
        calls = [a for a in legal if isinstance(a, (PonAction, ChiAction, KanAction))]
        if calls:
            return self._r.choice(calls)
        # 4. discard: prefer terminals/honors first
        discards = [a for a in legal if isinstance(a, DiscardAction)]
        if discards:
            scored = []
            for a in discards:
                t = _find_tile(state, a.tile_id)
                score = 0
                if t and t.suit == SUIT_Z:
                    score = 3
                elif t and getattr(t, "rank", 5) in (1, 9):
                    score = 1
                scored.append((score, self._r.random(), a))
            scored.sort(reverse=True)
            return scored[0][2]
        return self._r.choice(legal)


def _find_tile(state, tile_id):
    for z in state.zones.values():
        for t in z.items:
            if getattr(t, "id", None) == tile_id:
                return t
    for p in state.players.values():
        for z in p.zones.values():
            for t in z.items:
                if getattr(t, "id", None) == tile_id:
                    return t
                if hasattr(t, "tiles"):
                    for tt in t.tiles:
                        if tt.id == tile_id:
                            return tt
    return None


def run(seed: int, verbose: bool = True) -> dict:
    names = ["E", "S", "W", "N"]
    ruleset = RiichiRuleset()
    game = AbstractMahjongGame(ruleset, player_names=names)
    state = GameState(rng=RNG(seed=seed))
    providers = {i: WinSeekingAI(seed=seed * 7 + i) for i in range(4)}
    bus = EventBus()
    result = {"kind": "running"}

    def log(e: Event) -> None:
        if not verbose:
            if isinstance(e, HandWon):
                result["kind"] = "win"
            elif isinstance(e, HandDrawn):
                result["kind"] = "drawn"
            return
        if isinstance(e, HandStarted):
            print(f"-- Hand starts. Dealer: {names[e.dealer]}, round {['','E','S','W','N'][e.round_wind]} --")
        elif isinstance(e, TileDrawn):
            t = _find_tile(state, e.tile_id)
            tag = " (rinshan)" if e.from_dead_wall else ""
            print(f"  {names[e.seat]} draws {t}{tag}")
        elif isinstance(e, TileDiscarded):
            t = _find_tile(state, e.tile_id)
            tag = " RIICHI" if e.riichi else ""
            print(f"  {names[e.seat]} discards {t}{tag}")
        elif isinstance(e, MeldFormed):
            from_str = "" if e.called_from is None else f" from {names[e.called_from]}"
            print(f"  {names[e.seat]} {e.meld_type}{from_str}")
        elif isinstance(e, RiichiDeclared):
            pass  # paired with the discard event
        elif isinstance(e, HandWon):
            kind = "tsumo" if e.loser is None else f"ron from {names[e.loser]}"
            print(f"\n*** {names[e.winner]} wins by {kind}: +{e.score} ***")
            ya = state.attrs.get("mj_last_yaku", [])
            han = state.attrs.get("mj_last_han", 0)
            fu = state.attrs.get("mj_last_fu", 0)
            print(f"    {han} han / {fu} fu: {', '.join(f'{n}({v})' for n, v in ya)}")
            result["kind"] = "win"
        elif isinstance(e, HandDrawn):
            print("\n*** drawn (流局) ***")
            result["kind"] = "drawn"

    bus.subscribe(log)
    engine = Engine(game, state, providers, bus, max_steps=50_000)
    engine.run()

    if verbose:
        print("\nFinal:")
        for i in range(4):
            print(f"  {names[i]}: {state.players[i].resources['points'].value:+d}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=int(time.time()))
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    run(seed=args.seed, verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
