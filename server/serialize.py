"""Serialise engine objects → protocol DTOs.

The crucial bit is **per-seat state filtering**: when serialising for seat S, S sees
its own hand fully, but other seats' hands are only counted. Discards / melds / dora
indicators / wall count are public.
"""
from __future__ import annotations

from typing import cast

from core.event import Event
from core.state import GameState
from mahjong.abstract_game import (
    K_CURRENT,
    K_HAND_NUMBER,
    K_LAST_DRAWN_TILE,
    K_PHASE,
    K_ROUND_WIND,
)
from mahjong.actions import (
    ChiAction,
    DeclareAbortAction,
    DeclareRiichiAction,
    DeclareWinAction,
    DiscardAction,
    KanAction,
    PassAction,
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
from mahjong.meld import Meld
from mahjong.tile import Tile
from server.protocol import (
    ActionView,
    MeldView,
    SeatView,
    SnapshotMsg,
    TileView,
)


# ──────────────────────────────────────────────────────────────────────────
# value-object serialisers
# ──────────────────────────────────────────────────────────────────────────
def tile_view(t: Tile) -> TileView:
    return TileView(code=t.code, red=t.red, id=t.id)


def meld_view(m: Meld) -> MeldView:
    return MeldView(
        meld_type=m.meld_type,
        tiles=[tile_view(t) for t in m.tiles],
        called_from=m.called_from,
    )


# ──────────────────────────────────────────────────────────────────────────
# state snapshot for a given seat
# ──────────────────────────────────────────────────────────────────────────
def make_snapshot(state: GameState, your_seat: int) -> SnapshotMsg:
    seats: list[SeatView] = []
    for seat in sorted(state.players.keys()):
        p = state.players[seat]
        hand_zone = p.zones["hand"]
        melds = [cast(Meld, m) for m in p.zones["melds"].items]
        discards = [cast(Tile, t) for t in p.zones["discards"].items]
        sv = SeatView(
            seat=seat,
            name=p.name,
            points=p.resources["points"].value if "points" in p.resources else 0,
            riichi=bool(p.attrs.get("riichi")),
            melds=[meld_view(m) for m in melds],
            discards=[tile_view(t) for t in discards],
            hand=[tile_view(cast(Tile, t)) for t in hand_zone.items] if seat == your_seat else None,
            hand_count=len(hand_zone),
        )
        seats.append(sv)

    dora_zone = state.zones.get("dora_indicators")
    dora = [tile_view(cast(Tile, t)) for t in dora_zone.items] if dora_zone else []

    last_drawn = None
    if state.attrs.get(K_LAST_DRAWN_TILE) is not None and your_seat == state.attrs.get(K_CURRENT):
        tid = state.attrs[K_LAST_DRAWN_TILE]
        for t in state.players[your_seat].zones["hand"].items:
            if t.id == tid:
                last_drawn = tile_view(cast(Tile, t))
                break

    return SnapshotMsg(
        your_seat=your_seat,
        round_wind=cast(int, state.attrs.get(K_ROUND_WIND, 1)),
        hand_number=cast(int, state.attrs.get(K_HAND_NUMBER, 1)),
        dealer=cast(int, state.attrs.get("mj_dealer_seat", 0)),
        wall_count=len(state.zones.get("wall").items) if "wall" in state.zones else 0,  # type: ignore[union-attr]
        dead_wall_count=len(state.zones["dead_wall"].items) if "dead_wall" in state.zones else 0,
        dora_indicators=dora,
        seats=seats,
        current_seat=cast(int | None, state.attrs.get(K_CURRENT)),
        phase=cast(str | None, state.attrs.get(K_PHASE)),
        last_drawn_tile=last_drawn,
    )


# ──────────────────────────────────────────────────────────────────────────
# event serialisation (public-info only — hidden draws etc. for own seat)
# ──────────────────────────────────────────────────────────────────────────
def event_to_dict(event: Event, state: GameState, your_seat: int) -> dict | None:
    """Return a dict suitable for sending to the given client, or None if the event
    shouldn't be sent to them (e.g. an opponent's TileDrawn — we don't reveal the
    drawn tile to opponents)."""
    if isinstance(event, HandStarted):
        return {
            "kind": "hand_started",
            "dealer": event.dealer,
            "round_wind": event.round_wind,
            "hand_number": event.hand_number,
        }
    if isinstance(event, TileDrawn):
        d: dict = {
            "kind": "tile_drawn",
            "seat": event.seat,
            "from_dead_wall": event.from_dead_wall,
        }
        if event.seat == your_seat:
            tile = _find_tile_by_id(state, event.tile_id)
            if tile is not None:
                d["tile"] = tile_view(tile).to_dict()
        return d
    if isinstance(event, TileDiscarded):
        tile = _find_tile_by_id(state, event.tile_id)
        return {
            "kind": "tile_discarded",
            "seat": event.seat,
            "tile": tile_view(tile).to_dict() if tile else None,
            "riichi": event.riichi,
        }
    if isinstance(event, MeldFormed):
        # find the meld by id within the seat's melds zone
        p = state.players[event.seat]
        meld = next((m for m in p.zones["melds"].items if m.id == event.meld_id), None)
        return {
            "kind": "meld_formed",
            "seat": event.seat,
            "meld_type": event.meld_type,
            "called_from": event.called_from,
            "tiles": [tile_view(t).to_dict() for t in meld.tiles] if meld is not None else [],
        }
    if isinstance(event, RiichiDeclared):
        return {"kind": "riichi_declared", "seat": event.seat}
    if isinstance(event, HandWon):
        return {
            "kind": "hand_won",
            "winner": event.winner,
            "loser": event.loser,
            "score": event.score,
        }
    if isinstance(event, HandDrawn):
        d = {
            "kind": "hand_drawn",
            "tenpai_seats": list(event.tenpai_seats),
        }
        reason = state.attrs.get("mj_abort_reason")
        if reason:
            d["abort_reason"] = reason
        return d
    return None  # unknown event type — skip


def _find_tile_by_id(state: GameState, tile_id: int) -> Tile | None:
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


# ──────────────────────────────────────────────────────────────────────────
# action serialisation (we hand client a list of options with stable ids)
# ──────────────────────────────────────────────────────────────────────────
def action_views(actions: list, state: GameState) -> list[ActionView]:
    out: list[ActionView] = []
    for i, a in enumerate(actions):
        aid = f"a{i}"
        if isinstance(a, DiscardAction):
            t = _find_tile_by_id(state, a.tile_id)
            out.append(ActionView(id=aid, kind="discard", tiles=[tile_view(t)] if t else []))
        elif isinstance(a, PassAction):
            out.append(ActionView(id=aid, kind="pass"))
        elif isinstance(a, PonAction):
            tiles = [_find_tile_by_id(state, tid) for tid in a.hand_tile_ids]
            out.append(
                ActionView(id=aid, kind="pon", tiles=[tile_view(t) for t in tiles if t])
            )
        elif isinstance(a, ChiAction):
            tiles = [_find_tile_by_id(state, tid) for tid in a.hand_tile_ids]
            out.append(
                ActionView(id=aid, kind="chi", tiles=[tile_view(t) for t in tiles if t])
            )
        elif isinstance(a, KanAction):
            tiles = [_find_tile_by_id(state, tid) for tid in a.hand_tile_ids]
            out.append(
                ActionView(
                    id=aid,
                    kind="kan",
                    tiles=[tile_view(t) for t in tiles if t],
                    extra={"kan_kind": a.kind},
                )
            )
        elif isinstance(a, DeclareWinAction):
            out.append(ActionView(id=aid, kind=a.kind))   # "tsumo" or "ron"
        elif isinstance(a, DeclareRiichiAction):
            t = _find_tile_by_id(state, a.discard_tile_id)
            out.append(
                ActionView(
                    id=aid,
                    kind="riichi",
                    tiles=[tile_view(t)] if t else [],
                )
            )
        elif isinstance(a, DeclareAbortAction):
            out.append(
                ActionView(id=aid, kind="abort", extra={"reason": a.reason})
            )
        else:
            out.append(ActionView(id=aid, kind=f"unknown:{type(a).__name__}"))
    return out
