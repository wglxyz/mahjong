"""WebSocketProvider: an ActionProvider that talks to a remote client.

The engine is synchronous — `choose()` returns an Action. Our websockets server runs
in asyncio. We bridge with two thread-safe primitives:

  - `outbox` queue.Queue: engine thread pushes "please decide" packets here; the
    asyncio task that owns the WS pulls and sends.
  - `_response_event` + `_response_action`: asyncio task pushes the chosen action
    here; the engine thread blocks in `choose()` until the event fires.
"""
from __future__ import annotations
import queue
import threading
from typing import Any

from core.action import Action
from core.player import PlayerId
from core.state import GameState
from server.serialize import action_views, make_snapshot


class WebSocketProvider:
    def __init__(self, seat: PlayerId, outbox: "queue.Queue[dict[str, Any]]") -> None:
        self.seat = seat
        # outbox shared with the rest of the session, drained by the asyncio task
        self.outbox = outbox
        self._response_event = threading.Event()
        self._response_action: Action | None = None
        self._action_id_to_action: dict[str, Action] = {}
        self._closed = False

    # ---- called by the asyncio task that owns the WS connection -----------
    def deliver_response(self, action_id: str) -> bool:
        """Map an action id back to a real Action object, then unblock choose().
        Returns True if mapping found and accepted; False on bad id."""
        if action_id not in self._action_id_to_action:
            return False
        self._response_action = self._action_id_to_action[action_id]
        self._response_event.set()
        return True

    def close(self) -> None:
        """Wake any pending choose() so the engine thread can unwind."""
        self._closed = True
        self._response_action = None
        self._response_event.set()

    # ---- ActionProvider protocol — runs on the engine thread --------------
    def choose(self, state: GameState, me: PlayerId, legal: list[Action]) -> Action:
        if self._closed:
            raise RuntimeError("WebSocketProvider closed before decision returned")

        # build action views with stable ids; remember mapping
        views = action_views(legal, state)
        self._action_id_to_action = {v.id: a for v, a in zip(views, legal)}

        # send a snapshot first so the client always has fresh state to render the prompt against
        snap = make_snapshot(state, your_seat=self.seat).to_dict()
        self.outbox.put(snap)
        self.outbox.put(
            {
                "type": "decision",
                "actions": [v.to_dict() for v in views],
            }
        )

        # wait
        self._response_event.wait()
        self._response_event.clear()

        if self._closed or self._response_action is None:
            raise RuntimeError("WebSocketProvider closed mid-decision")
        action = self._response_action
        self._response_action = None
        return action
