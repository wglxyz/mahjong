"""Smoke test: AbstractMahjongGame + SimpleRuleset never crashes across many seeds,
points stay zero-sum, terminal state is consistent."""
from __future__ import annotations

import random as _random

from core.action import Action
from core.engine import Engine
from core.event_bus import EventBus
from core.player import PlayerId
from core.rng import RNG
from core.state import GameState
from mahjong.abstract_game import K_RESULT, AbstractMahjongGame
from mahjong.actions import DeclareWinAction, PonAction
from rules.simple import SimpleRuleset


class WinSeekingProvider:
    def __init__(self, seed: int) -> None:
        self._r = _random.Random(seed)

    def choose(self, state: GameState, me: PlayerId, legal: list[Action]) -> Action:
        for a in legal:
            if isinstance(a, DeclareWinAction):
                return a
        for a in legal:
            if isinstance(a, PonAction):
                return a
        return self._r.choice(legal)


def run_one(seed: int) -> dict:
    game = AbstractMahjongGame(SimpleRuleset(), player_names=["E","S","W","N"])
    state = GameState(rng=RNG(seed=seed))
    providers = {i: WinSeekingProvider(seed=seed * 7 + i) for i in range(4)}
    engine = Engine(game, state, providers, EventBus(), max_steps=20_000)
    winners = engine.run()
    points = {i: state.players[i].resources["points"].value for i in range(4)}
    return {
        "winners": winners,
        "points": points,
        "result": state.attrs.get(K_RESULT),
    }


def test_runs_to_termination_across_seeds() -> None:
    for seed in range(40):
        r = run_one(seed)
        assert r["result"] in ("win", "drawn"), f"seed {seed}: unexpected result {r['result']}"


def test_points_conservation() -> None:
    """With initial_points=25000 across 4 seats, the table total must stay at 100000."""
    expected = 25000 * 4
    for seed in range(20):
        r = run_one(seed)
        total = sum(r["points"].values())
        assert total == expected, f"seed {seed}: total {total} != {expected}: {r['points']}"


def test_winner_above_starting_on_win() -> None:
    saw_a_win = False
    for seed in range(60):
        r = run_one(seed)
        if r["result"] == "win":
            saw_a_win = True
            assert len(r["winners"]) >= 1
            w = r["winners"][0]
            assert r["points"][w] > 25000, f"seed {seed}: winner {w} below starting: {r['points']}"
    assert saw_a_win, "expected at least one match-end win across 60 seeds"


def test_determinism() -> None:
    a = run_one(seed=11)
    b = run_one(seed=11)
    assert a == b


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items() if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f()
        print(f"  ✓ {n}")
    print(f"\n{len(fns)} tests passed")
