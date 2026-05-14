from __future__ import annotations

from core.action import Action
from core.action_provider import ActionProvider
from core.event_bus import EventBus
from core.game_def import GameDef
from core.player import PlayerId
from core.state import GameState


class Engine:
    """Drives a GameDef. Knows nothing about specific games — just the loop:

        setup -> while not terminal: ask decision-point -> collect actions -> apply -> broadcast events
    """

    def __init__(
        self,
        game: GameDef,
        state: GameState,
        providers: dict[PlayerId, ActionProvider],
        bus: EventBus | None = None,
        max_steps: int = 10_000,
    ) -> None:
        self.game = game
        self.state = state
        self.providers = providers
        self.bus = bus or EventBus()
        self.max_steps = max_steps

    def run(self) -> list[PlayerId]:
        setup_events = self.game.setup(self.state) or []
        for e in setup_events:
            self.bus.publish(e)
        steps = 0
        while not self.game.is_terminal(self.state):
            if steps >= self.max_steps:
                raise RuntimeError(f"engine exceeded max_steps={self.max_steps}; possible infinite loop")
            steps += 1

            dp = self.game.decision_point(self.state)
            if dp is None:
                break

            decisions: dict[PlayerId, Action] = {}
            for pid, legal in dp.legal_actions.items():
                if not legal:
                    raise RuntimeError(f"player {pid} has no legal actions at decision point")
                action = self.providers[pid].choose(self.state, pid, legal)
                if action not in legal:
                    raise RuntimeError(f"player {pid} returned illegal action {action}")
                decisions[pid] = action

            events = self.game.apply(self.state, decisions)
            for e in events:
                self.bus.publish(e)

        return self.game.winners(self.state)
