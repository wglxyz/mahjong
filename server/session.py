"""Session: one table, one WS-connected client, three AIs.

Game engine runs in a daemon thread. Events flow:
  engine → EventBus subscriber (this Session) → outbox queue → asyncio task → WS
  WS → asyncio task → WebSocketProvider.deliver_response() → engine unblocks
"""
from __future__ import annotations

import queue
import random as _random
import threading
import time
from typing import Any

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
    PassAction,
    PonAction,
)
from server.protocol import HandEndedMsg, MatchEndedMsg, WelcomeMsg
from server.serialize import event_to_dict, make_snapshot
from server.ws_provider import WebSocketProvider


# ──────────────────────────────────────────────────────────────────────────
# AI provider (same heuristic as games/mahjong/play_riichi.py, condensed)
# ──────────────────────────────────────────────────────────────────────────
class HouseAI:
    def __init__(self, seed: int) -> None:
        self._r = _random.Random(seed)

    def choose(self, state, me, legal):
        from mahjong.actions import DiscardAction
        from mahjong.tile import SUIT_Z
        for a in legal:
            if isinstance(a, DeclareWinAction):
                return a
        for a in legal:
            if isinstance(a, DeclareRiichiAction):
                return a
        calls = [a for a in legal if isinstance(a, (PonAction, ChiAction, KanAction))]
        if calls:
            return self._r.choice(calls)
        passes = [a for a in legal if isinstance(a, PassAction)]
        if passes:
            return passes[0]
        discards = [a for a in legal if isinstance(a, DiscardAction)]
        if discards:
            scored = []
            for a in discards:
                t = _find(state, a.tile_id)
                score = 0
                if t and t.suit == SUIT_Z:
                    score = 3
                elif t and getattr(t, "rank", 5) in (1, 9):
                    score = 1
                scored.append((score, self._r.random(), a))
            scored.sort(reverse=True)
            return scored[0][2]
        return self._r.choice(legal)


def _find(state, tile_id):
    for z in state.zones.values():
        for t in z.items:
            if getattr(t, "id", None) == tile_id:
                return t
    for p in state.players.values():
        for z in p.zones.values():
            for t in z.items:
                if getattr(t, "id", None) == tile_id:
                    return t
    return None


# ──────────────────────────────────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────────────────────────────────
class Session:
    def __init__(
        self,
        ruleset_name: str,
        human_seat: int = 0,
        seed: int | None = None,
    ) -> None:
        self.ruleset_name = ruleset_name
        self.human_seat = human_seat
        self.seed = seed if seed is not None else int(time.time())
        self.outbox: queue.Queue[dict[str, Any]] = queue.Queue()
        self.ws_provider = WebSocketProvider(seat=human_seat, outbox=self.outbox)
        self._build_game()
        self._engine_thread: threading.Thread | None = None
        self._closed = False

    # ---- public ------------------------------------------------------------
    def welcome_message(self) -> dict:
        return WelcomeMsg(
            your_seat=self.human_seat,
            seats=self.player_names,
            ruleset=self.ruleset_name,
        ).to_dict()

    def initial_snapshot(self) -> dict:
        # called after the engine has set up; we may need to give the engine a moment.
        # safe to call once at_start completes.
        return make_snapshot(self.state, your_seat=self.human_seat).to_dict()

    def deliver_decision(self, action_id: str) -> bool:
        return self.ws_provider.deliver_response(action_id)

    def start(self) -> None:
        """Start the engine in a background thread."""
        if self._engine_thread is not None:
            return
        self._engine_thread = threading.Thread(target=self._run_engine, daemon=True, name=f"engine-{id(self)}")
        self._engine_thread.start()

    def close(self) -> None:
        self._closed = True
        self.ws_provider.close()

    def is_running(self) -> bool:
        return self._engine_thread is not None and self._engine_thread.is_alive()

    # ---- internals ---------------------------------------------------------
    def _build_game(self) -> None:
        self.player_names = ["E", "S", "W", "N"]
        if self.ruleset_name == "riichi":
            from rules.riichi.ruleset import RiichiRuleset
            ruleset = RiichiRuleset()
        else:
            from rules.simple import SimpleRuleset
            ruleset = SimpleRuleset()
        self.game = AbstractMahjongGame(ruleset, player_names=self.player_names)
        self.state = GameState(rng=RNG(seed=self.seed))
        self.providers: dict[PlayerId, Any] = {
            self.human_seat: self.ws_provider,
        }
        for i in range(4):
            if i == self.human_seat:
                continue
            self.providers[i] = HouseAI(seed=self.seed * 7 + i)
        self.bus = EventBus()
        self.bus.subscribe(self._on_event)
        self.engine = Engine(self.game, self.state, self.providers, self.bus, max_steps=50_000)

    def _on_event(self, e: Event) -> None:
        d = event_to_dict(e, self.state, your_seat=self.human_seat)
        if d is None:
            return
        self.outbox.put({"type": "event", "event": d})

        # hand ended → also send a HandEndedMsg with score detail
        from mahjong.events import HandDrawn, HandWon
        if isinstance(e, HandWon):
            yaku = self.state.attrs.get("mj_last_yaku") or []
            winners = list(self.state.attrs.get("mj_winners") or [e.winner])
            self.outbox.put(
                HandEndedMsg(
                    result="win",
                    winner=e.winner,
                    loser=e.loser,
                    score=e.score,
                    han=self.state.attrs.get("mj_last_han"),
                    fu=self.state.attrs.get("mj_last_fu"),
                    yaku=[tuple(y) for y in yaku],
                    winners=winners,
                ).to_dict()
            )
        elif isinstance(e, HandDrawn):
            self.outbox.put(
                HandEndedMsg(
                    result="drawn",
                    winner=None,
                    loser=None,
                    score=0,
                    han=None,
                    fu=None,
                    yaku=[],
                    winners=[],
                    abort_reason=self.state.attrs.get("mj_abort_reason"),
                ).to_dict()
            )

    def _run_engine(self) -> None:
        try:
            self.engine.run()
        except RuntimeError as exc:
            # most likely ws_provider closed mid-decision
            self.outbox.put({"type": "error", "error": str(exc)})
        finally:
            # if the engine reached a clean match end, emit a summary first
            from mahjong.abstract_game import K_PHASE, PHASE_END, K_HAND_RESULTS
            if self.state.attrs.get(K_PHASE) == PHASE_END:
                self.outbox.put(
                    MatchEndedMsg(
                        final_points={
                            i: p.resources["points"].value
                            for i, p in self.state.players.items()
                        },
                        hand_results=list(self.state.attrs.get(K_HAND_RESULTS, [])),
                    ).to_dict()
                )
            self.outbox.put({"type": "_end"})  # sentinel for the ws coroutine
