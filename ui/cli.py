"""Terminal UI for mahjong (and any game built on the same primitives).

Two pieces:
  - CLIProvider — an ActionProvider that prompts the user on stdin.
  - CLILogger   — subscribes to the EventBus, prints brief per-event lines plus a
                   final results panel.

Neither is mahjong-specific in its core wiring; the action-description helpers are.
"""
from __future__ import annotations

import sys
from typing import cast

from core.action import Action
from core.player import PlayerId
from core.state import GameState
from mahjong.abstract_game import (
    K_HAND_NUMBER,
    K_LAST_DISCARD_SEAT,
    K_LAST_DISCARD_TILE,
    K_LAST_DRAWN_TILE,
    K_PHASE,
    K_ROUND_WIND,
    PHASE_RESPONSE,
)
from mahjong.actions import (
    ChiAction,
    DeclareRiichiAction,
    DeclareWinAction,
    DiscardAction,
    KanAction,
    PassAction,
    PonAction,
)
from mahjong.events import (
    HandDrawn,
    HandWon,
    MeldFormed,
    RiichiDeclared,
    TileDiscarded,
    TileDrawn,
)
from mahjong.meld import Meld
from mahjong.tile import Tile

_SUIT_ORDER = {"m": 0, "p": 1, "s": 2, "z": 3, "f": 4}


def _sort_tiles(tiles: list[Tile]) -> list[Tile]:
    return sorted(tiles, key=lambda t: (_SUIT_ORDER.get(t.suit, 9), t.rank, not t.red))


def _format_meld(m: Meld) -> str:
    body = " ".join(repr(t) for t in m.tiles)
    return f"[{m.meld_type}: {body}]"


def _find_tile(state: GameState, tile_id: int) -> Tile | None:
    for z in state.zones.values():
        for t in z.items:
            if t.id == tile_id:
                return cast(Tile, t)
    for p in state.players.values():
        for z in p.zones.values():
            for t in z.items:
                if isinstance(t, Meld):
                    for tt in t.tiles:
                        if tt.id == tile_id:
                            return tt
                elif t.id == tile_id:
                    return cast(Tile, t)
    return None


class CLIProvider:
    """Prompts the user via stdin when it's their turn.

    If the only legal action is PassAction, returns it without prompting (keeps
    response windows quiet when the player has nothing real to choose).
    """

    def __init__(self, seat: PlayerId, names: list[str]) -> None:
        self.seat = seat
        self.names = names

    def choose(self, state: GameState, me: PlayerId, legal: list[Action]) -> Action:
        if len(legal) == 1 and isinstance(legal[0], PassAction):
            return legal[0]

        self._render_table(state)
        self._render_prompt_header(state)

        for i, action in enumerate(legal, 1):
            print(f"  [{i}] {self._describe(action, state)}")

        while True:
            try:
                raw = input("\n> ").strip()
            except EOFError:
                print()
                sys.exit(0)
            if not raw:
                continue
            try:
                idx = int(raw) - 1
            except ValueError:
                print(f"  enter a number 1-{len(legal)}")
                continue
            if 0 <= idx < len(legal):
                return legal[idx]
            print(f"  enter a number 1-{len(legal)}")

    # ---- rendering ---------------------------------------------------------
    def _render_table(self, state: GameState) -> None:
        wall = state.zones["wall"]
        rw = state.attrs.get(K_ROUND_WIND, 1)
        hn = state.attrs.get(K_HAND_NUMBER, 1)
        print()
        print("─" * 72)
        print(f"Round {['','E','S','W','N'][rw]}{hn}    wall: {len(wall)} tiles left")
        last_drawn = state.attrs.get(K_LAST_DRAWN_TILE)

        for seat in range(len(self.names)):
            p = state.players[seat]
            mark = "★" if seat == self.seat else " "
            label = "You" if seat == self.seat else self.names[seat]

            hand_zone = p.zones["hand"]
            if seat == self.seat:
                tiles = _sort_tiles([cast(Tile, t) for t in hand_zone.items])
                parts = []
                for t in tiles:
                    s = repr(t)
                    if last_drawn is not None and t.id == last_drawn:
                        s = f"[{s}]"
                    parts.append(s)
                hand_str = " ".join(parts)
            else:
                hand_str = f"({len(hand_zone)} tiles)"

            melds = [cast(Meld, m) for m in p.zones["melds"].items]
            melds_str = " ".join(_format_meld(m) for m in melds) if melds else ""

            disc_tiles = [cast(Tile, t) for t in p.zones["discards"].items]
            disc_str = " ".join(repr(t) for t in disc_tiles) if disc_tiles else ""

            pts = p.resources["points"].value
            print(f"{mark} {label:>3}  ({pts:+d})  {hand_str}")
            if melds_str:
                print(f"            melds:    {melds_str}")
            if disc_str:
                print(f"            discards: {disc_str}")
        print("─" * 72)

    def _render_prompt_header(self, state: GameState) -> None:
        phase = state.attrs.get(K_PHASE)
        if phase == PHASE_RESPONSE:
            d_seat = state.attrs.get(K_LAST_DISCARD_SEAT)
            t_id = state.attrs.get(K_LAST_DISCARD_TILE)
            tile = _find_tile(state, t_id) if t_id is not None else None
            who = self.names[d_seat] if d_seat is not None else "?"
            print(f"\n{who} discarded {tile} — your call?")
        else:
            print("\nYour turn:")

    def _describe(self, action: Action, state: GameState) -> str:
        if isinstance(action, DiscardAction):
            t = _find_tile(state, action.tile_id)
            return f"discard {t}"
        if isinstance(action, PassAction):
            return "pass"
        if isinstance(action, PonAction):
            t1 = _find_tile(state, action.hand_tile_ids[0])
            return f"pon ({t1} {t1})"
        if isinstance(action, ChiAction):
            tiles = [_find_tile(state, tid) for tid in action.hand_tile_ids]
            return f"chi ({' '.join(repr(t) for t in tiles)})"
        if isinstance(action, KanAction):
            return f"kan ({action.kind})"
        if isinstance(action, DeclareWinAction):
            return "TSUMO!" if action.kind == "tsumo" else "RON!"
        if isinstance(action, DeclareRiichiAction):
            t = _find_tile(state, action.discard_tile_id)
            return f"riichi (discard {t})"
        return repr(action)


class CLILogger:
    """Subscribe an instance's `.on_event` to the EventBus.

    Prints a short line per public event so the user can follow what other seats do
    between their own prompts.
    """

    def __init__(self, names: list[str], human_seat: PlayerId, state: GameState) -> None:
        self.names = names
        self.human_seat = human_seat
        self.state = state

    def _seat(self, seat: PlayerId) -> str:
        return "you" if seat == self.human_seat else self.names[seat]

    def on_event(self, event) -> None:
        if isinstance(event, TileDrawn):
            return  # too noisy; the human sees their own draw via the rendered hand
        if isinstance(event, TileDiscarded):
            t = _find_tile(self.state, event.tile_id)
            tag = " [riichi!]" if event.riichi else ""
            print(f"  → {self._seat(event.seat)} discards {t}{tag}")
            return
        if isinstance(event, MeldFormed):
            from_str = ""
            if event.called_from is not None:
                from_str = f" (from {self._seat(event.called_from)})"
            print(f"  → {self._seat(event.seat)} calls {event.meld_type}{from_str}")
            return
        if isinstance(event, RiichiDeclared):
            return  # paired TileDiscarded already has the riichi tag
        if isinstance(event, HandWon):
            kind = "tsumo" if event.loser is None else f"ron from {self._seat(event.loser)}"
            who = self._seat(event.winner)
            print(f"\n*** {who} wins by {kind}!  (+{event.score}) ***")
            return
        if isinstance(event, HandDrawn):
            print("\n*** drawn game (流局) ***")
            return
