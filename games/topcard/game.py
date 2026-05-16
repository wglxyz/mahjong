"""TopCard: a minimal game built only on L1 primitives.

Rules: N players share a hidden deck. On your turn, draw the top card to your public
score pile and add its value to your score resource. Highest score when deck empties wins.

Purpose: validate that the L1 abstractions can express a real (if trivial) game without
the game module touching engine internals.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.action import Action
from core.entity import Entity
from core.event import Event
from core.game_def import DecisionPoint
from core.player import Player, PlayerId
from core.resource import Resource
from core.state import GameState
from core.zone import Ordering, Visibility, Zone


class Card(Entity):
    def __init__(self, value: int) -> None:
        super().__init__()
        self.value = value

    def __repr__(self) -> str:
        return f"Card({self.value})"


@dataclass(frozen=True)
class DrawAction(Action):
    pass


@dataclass(frozen=True)
class CardDrawn(Event):
    player: PlayerId
    card_value: int


@dataclass(frozen=True)
class GameOver(Event):
    scores: tuple[tuple[PlayerId, int], ...]
    winners: tuple[PlayerId, ...]


CURRENT_KEY = "current_player"


class TopCardGame:
    def __init__(self, player_names: list[str], deck_size: int = 20) -> None:
        self.player_names = player_names
        self.deck_size = deck_size

    def setup(self, state: GameState) -> list[Event]:
        deck = Zone(name="deck", visibility=Visibility.HIDDEN, ordering=Ordering.ORDERED)
        for v in range(1, self.deck_size + 1):
            deck.push(Card(v))
        state.rng.shuffle(deck.items)
        state.zones["deck"] = deck

        for i, name in enumerate(self.player_names):
            p = Player(id=i, name=name)
            p.zones["score_pile"] = Zone(
                name="score_pile",
                visibility=Visibility.PUBLIC,
                ordering=Ordering.UNORDERED,
                owner=i,
            )
            p.resources["score"] = Resource(name="score", value=0, minimum=0)
            state.players[i] = p

        state.phase = "play"
        state.turn = 0
        state.attrs[CURRENT_KEY] = state.player_order()[0]
        return []

    def decision_point(self, state: GameState) -> DecisionPoint | None:
        if self.is_terminal(state):
            return None
        current: PlayerId = state.attrs[CURRENT_KEY]  # type: ignore[assignment]
        return DecisionPoint(legal_actions={current: [DrawAction(actor=current)]})

    def apply(self, state: GameState, decisions: dict[PlayerId, Action]) -> list[Event]:
        events: list[Event] = []

        for pid, action in decisions.items():
            if isinstance(action, DrawAction):
                deck = state.zones["deck"]
                card = deck.pop()  # top of deck
                assert isinstance(card, Card)
                player = state.players[pid]
                player.zones["score_pile"].push(card)
                player.resources["score"].adjust(card.value)
                events.append(CardDrawn(player=pid, card_value=card.value))

        # advance turn
        order = state.player_order()
        cur: PlayerId = state.attrs[CURRENT_KEY]  # type: ignore[assignment]
        state.attrs[CURRENT_KEY] = order[(order.index(cur) + 1) % len(order)]
        state.turn += 1

        if self.is_terminal(state):
            scores = tuple((pid, state.players[pid].resources["score"].value) for pid in order)
            events.append(GameOver(scores=scores, winners=tuple(self.winners(state))))

        return events

    def is_terminal(self, state: GameState) -> bool:
        return state.zones["deck"].is_empty()

    def winners(self, state: GameState) -> list[PlayerId]:
        if not state.players:
            return []
        scores = {pid: state.players[pid].resources["score"].value for pid in state.players}
        top = max(scores.values())
        return [pid for pid, s in scores.items() if s == top]
