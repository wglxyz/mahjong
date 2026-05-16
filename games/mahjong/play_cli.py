"""Play SimpleRuleset mahjong: you are seat E (south player visually, but called E),
three AIs hold the other seats. Optional --seed for reproducibility."""
from __future__ import annotations

import argparse
import random as _random
import sys
import time

from core.action import Action
from core.engine import Engine
from core.event_bus import EventBus
from core.player import PlayerId
from core.rng import RNG
from core.state import GameState
from mahjong.abstract_game import AbstractMahjongGame
from mahjong.actions import DeclareWinAction, PonAction
from rules.simple import SimpleRuleset
from ui.cli import CLILogger, CLIProvider


class WinSeekingAI:
    """Same heuristic as in tests: take any win, then any pon, else random."""

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=int(time.time()), help="RNG seed (default: time-based)")
    parser.add_argument("--seat", type=int, default=0, choices=[0, 1, 2, 3], help="your seat 0=E .. 3=N")
    args = parser.parse_args(argv)

    names = ["E", "S", "W", "N"]
    ruleset = SimpleRuleset()
    game = AbstractMahjongGame(ruleset, player_names=names)
    state = GameState(rng=RNG(seed=args.seed))

    providers: dict[PlayerId, object] = {}
    for i in range(4):
        if i == args.seat:
            providers[i] = CLIProvider(seat=i, names=names)
        else:
            providers[i] = WinSeekingAI(seed=args.seed * 7 + i)

    bus = EventBus()
    logger = CLILogger(names=names, human_seat=args.seat, state=state)
    bus.subscribe(logger.on_event)

    print(f"seed={args.seed}    you are {names[args.seat]}.")

    engine = Engine(game, state, providers, bus, max_steps=20_000)  # type: ignore[arg-type]
    engine.run()

    print("\nFinal:")
    for i in range(4):
        mark = "★" if i == args.seat else " "
        print(f"  {mark} {names[i]}: {state.players[i].resources['points'].value:+d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
