"""Wire protocol for server↔client.

All messages are dict-shaped JSON. We define them with dataclasses (typed authoring
sugar) plus dict-form `to_dict()` / `from_dict()` to keep ourselves honest. Frontend
clients (Flutter, web) deserialise the same shapes from the wire.

Direction conventions:
  S→C   server → client
  C→S   client → server

All S→C messages carry `type` discriminator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ──────────────────────────────────────────────────────────────────────────
# Tile / Meld value objects (serialised forms)
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class TileView:
    code: str           # "m5", "p3", "z1", ...
    red: bool = False
    id: int | None = None  # entity id, optional (clients may use for animations)

    def to_dict(self) -> dict:
        d = {"code": self.code}
        if self.red:
            d["red"] = True
        if self.id is not None:
            d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> TileView:
        return cls(code=d["code"], red=d.get("red", False), id=d.get("id"))


@dataclass
class MeldView:
    meld_type: str          # "chi" | "pon" | "minkan" | "ankan" | "shouminkan"
    tiles: list[TileView]
    called_from: int | None = None

    def to_dict(self) -> dict:
        return {
            "meld_type": self.meld_type,
            "tiles": [t.to_dict() for t in self.tiles],
            "called_from": self.called_from,
        }

    @classmethod
    def from_dict(cls, d: dict) -> MeldView:
        return cls(
            meld_type=d["meld_type"],
            tiles=[TileView.from_dict(t) for t in d["tiles"]],
            called_from=d.get("called_from"),
        )


@dataclass
class SeatView:
    seat: int
    name: str
    points: int
    riichi: bool
    melds: list[MeldView]
    discards: list[TileView]
    hand: list[TileView] | None = None   # set only for own seat; otherwise None
    hand_count: int = 0

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "seat": self.seat,
            "name": self.name,
            "points": self.points,
            "riichi": self.riichi,
            "melds": [m.to_dict() for m in self.melds],
            "discards": [t.to_dict() for t in self.discards],
            "hand_count": self.hand_count,
        }
        if self.hand is not None:
            d["hand"] = [t.to_dict() for t in self.hand]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> SeatView:
        return cls(
            seat=d["seat"],
            name=d["name"],
            points=d["points"],
            riichi=d.get("riichi", False),
            melds=[MeldView.from_dict(m) for m in d.get("melds", [])],
            discards=[TileView.from_dict(t) for t in d.get("discards", [])],
            hand=[TileView.from_dict(t) for t in d["hand"]] if "hand" in d else None,
            hand_count=d.get("hand_count", 0),
        )


# ──────────────────────────────────────────────────────────────────────────
# Action view: server gives client a stable id, client returns it
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class ActionView:
    id: str                     # opaque token; the server maps back to a real Action
    kind: str                   # "discard" | "pass" | "chi" | "pon" | "kan" | "tsumo" | "ron" | "riichi"
    tiles: list[TileView] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)   # e.g. {"kan_kind":"ankan"} or {"discard_after_riichi":"m5"}

    def to_dict(self) -> dict:
        d: dict = {"id": self.id, "kind": self.kind}
        if self.tiles:
            d["tiles"] = [t.to_dict() for t in self.tiles]
        if self.extra:
            d["extra"] = self.extra
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ActionView:
        return cls(
            id=d["id"],
            kind=d["kind"],
            tiles=[TileView.from_dict(t) for t in d.get("tiles", [])],
            extra=d.get("extra", {}),
        )


# ──────────────────────────────────────────────────────────────────────────
# S → C messages
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class WelcomeMsg:
    """First message after connect — tells the client which seat it owns."""
    your_seat: int
    seats: list[str]            # display names
    ruleset: str                # "simple" | "riichi"
    type: str = "welcome"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SnapshotMsg:
    """Full table state from your_seat's perspective. Sent on connect, before each
    decision, and after any hand-ending event."""
    your_seat: int
    round_wind: int
    hand_number: int
    dealer: int
    wall_count: int
    dead_wall_count: int
    dora_indicators: list[TileView]
    seats: list[SeatView]
    current_seat: int | None
    phase: str | None
    last_drawn_tile: TileView | None
    type: str = "snapshot"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "your_seat": self.your_seat,
            "round_wind": self.round_wind,
            "hand_number": self.hand_number,
            "dealer": self.dealer,
            "wall_count": self.wall_count,
            "dead_wall_count": self.dead_wall_count,
            "dora_indicators": [t.to_dict() for t in self.dora_indicators],
            "seats": [s.to_dict() for s in self.seats],
            "current_seat": self.current_seat,
            "phase": self.phase,
            "last_drawn_tile": self.last_drawn_tile.to_dict() if self.last_drawn_tile else None,
        }


@dataclass
class EventMsg:
    """A single game event. Client may apply incrementally; if it loses sync, request snapshot."""
    event: dict           # serialised event (kind + payload), produced by serialize.py
    type: str = "event"

    def to_dict(self) -> dict:
        return {"type": self.type, "event": self.event}


@dataclass
class DecisionMsg:
    """Server is waiting for the client to pick one of `actions`."""
    actions: list[ActionView]
    deadline_ms: int | None = None
    type: str = "decision"

    def to_dict(self) -> dict:
        d: dict = {"type": self.type, "actions": [a.to_dict() for a in self.actions]}
        if self.deadline_ms is not None:
            d["deadline_ms"] = self.deadline_ms
        return d


@dataclass
class HandEndedMsg:
    result: str                       # "win" | "drawn"
    winner: int | None
    loser: int | None                 # ron'd player (None for tsumo / drawn)
    score: int
    han: int | None
    fu: int | None
    yaku: list[tuple[str, int]]
    winners: list[int] = field(default_factory=list)   # all winners (≥1 for double-ron)
    abort_reason: str | None = None                    # set on aborted draws
    type: str = "hand_ended"

    def to_dict(self) -> dict:
        d = {
            "type": self.type,
            "result": self.result,
            "winner": self.winner,
            "loser": self.loser,
            "score": self.score,
            "han": self.han,
            "fu": self.fu,
            "yaku": [list(y) for y in self.yaku],
            "winners": list(self.winners),
        }
        if self.abort_reason is not None:
            d["abort_reason"] = self.abort_reason
        return d


@dataclass
class MatchEndedMsg:
    """Sent once after the entire match ends (all configured rounds played)."""
    final_points: dict[int, int]
    hand_results: list[dict]          # snapshots from state.attrs["mj_hand_results"]
    type: str = "match_ended"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "final_points": {str(k): v for k, v in self.final_points.items()},
            "hand_results": list(self.hand_results),
        }


@dataclass
class ErrorMsg:
    error: str
    type: str = "error"

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────────
# C → S messages
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class DecideMsg:
    action_id: str
    type: str = "decide"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> DecideMsg:
        return cls(action_id=d["action_id"])


@dataclass
class RequestSnapshotMsg:
    type: str = "request_snapshot"

    @classmethod
    def from_dict(cls, d: dict) -> RequestSnapshotMsg:
        return cls()
