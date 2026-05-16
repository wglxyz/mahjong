"""Smoke test: TopCard runs deterministically and reaches a valid terminal state."""
from __future__ import annotations

import random as _random

from core.action import Action
from core.engine import Engine
from core.event_bus import EventBus
from core.player import PlayerId
from core.rng import RNG
from core.state import GameState
from games.topcard.game import TopCardGame


class RandomProvider:
    def __init__(self, seed: int) -> None:
        self._r = _random.Random(seed)

    def choose(self, state, me: PlayerId, legal: list[Action]) -> Action:
        return self._r.choice(legal)


def run(seed: int, deck_size: int = 15) -> tuple[list[PlayerId], dict[PlayerId, int]]:
    names = ["A", "B", "C"]
    game = TopCardGame(player_names=names, deck_size=deck_size)
    state = GameState(rng=RNG(seed=seed))
    providers = {i: RandomProvider(seed=seed + i) for i in range(len(names))}
    engine = Engine(game, state, providers, EventBus())
    winners = engine.run()
    scores = {pid: state.players[pid].resources["score"].value for pid in state.players}
    return winners, scores


def test_terminates_and_conserves_points() -> None:
    winners, scores = run(seed=42)
    assert winners, "must have at least one winner"
    assert sum(scores.values()) == sum(range(1, 16)), "all card values must be accounted for"
    top = max(scores.values())
    assert all(scores[w] == top for w in winners), "winners must share the top score"


def test_deterministic() -> None:
    a = run(seed=7)
    b = run(seed=7)
    assert a == b


if __name__ == "__main__":
    test_terminates_and_conserves_points()
    test_deterministic()
    print("OK")
