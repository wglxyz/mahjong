"""Run TopCard with random AI providers and print the event log."""
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
from games.topcard.game import CardDrawn, GameOver, TopCardGame


class RandomProvider:
    def __init__(self, seed: int = 0) -> None:
        self._r = _random.Random(seed)

    def choose(self, state: GameState, me: PlayerId, legal: list[Action]) -> Action:
        return self._r.choice(legal)


def main(seed: int = 42) -> int:
    names = ["Alice", "Bob", "Carol"]
    game = TopCardGame(player_names=names, deck_size=15)
    state = GameState(rng=RNG(seed=seed))
    providers = {i: RandomProvider(seed=seed + i) for i in range(len(names))}
    bus = EventBus()

    def log(e: Event) -> None:
        if isinstance(e, CardDrawn):
            print(f"  {state.players[e.player].name} drew a {e.card_value}")
        elif isinstance(e, GameOver):
            print("\nFinal scores:")
            for pid, s in e.scores:
                print(f"  {state.players[pid].name}: {s}")
            names_w = ", ".join(state.players[p].name for p in e.winners)
            print(f"Winner(s): {names_w}")

    bus.subscribe(log)

    engine = Engine(game, state, providers, bus)
    winners = engine.run()
    return 0 if winners else 1


if __name__ == "__main__":
    sys.exit(main())
