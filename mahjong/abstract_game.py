"""AbstractMahjongGame: implements GameDef. Owns the phase machine and all state
mutation. Delegates every dialect-specific question to a Ruleset.

Phase machine:

    setup  ──► AFTER_DRAW (dealer's first turn, dealer has already drawn)

    AFTER_DRAW ── Discard ──► RESPONSE
                ── DeclareWin(tsumo) ──► END
                ── KanAction(ankan|shouminkan) ──► AFTER_DRAW (with rinshan)
                ── DeclareRiichi(+ discard) ──► RESPONSE

    RESPONSE   ── (all Pass) ──► AFTER_DRAW for next seat (auto-draw); or END if wall exhausted
                ── DeclareWin(ron) ──► END
                ── Chi/Pon ──► AFTER_CALL for caller
                ── Kan(minkan) ──► AFTER_DRAW for caller (with rinshan)

    AFTER_CALL ── Discard ──► RESPONSE
"""
from __future__ import annotations
from typing import cast

from core.action import Action
from core.event import Event
from core.game_def import DecisionPoint
from core.player import Player, PlayerId
from core.resource import Resource
from core.state import GameState
from core.zone import Ordering, Visibility, Zone

from mahjong.actions import (
    ChiAction,
    DeclareRiichiAction,
    DeclareWinAction,
    DiscardAction,
    KanAction,
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
from mahjong.meld import ANKAN, CHI, MINKAN, PON, SHOUMINKAN, Meld
from mahjong.ruleset import Ruleset
from mahjong.tile import Tile

# ---- phase constants -------------------------------------------------------
PHASE_AFTER_DRAW = "after_draw"
PHASE_RESPONSE = "response"
PHASE_AFTER_CALL = "after_call"
PHASE_END = "end"

# ---- state.attrs keys ------------------------------------------------------
K_PHASE = "mj_phase"
K_CURRENT = "mj_current_seat"
K_LAST_DISCARD_TILE = "mj_last_discard_tile_id"
K_LAST_DISCARD_SEAT = "mj_last_discard_seat"
K_LAST_DRAWN_TILE = "mj_last_drawn_tile_id"
K_RESULT = "mj_result"
K_WINNER = "mj_winner_seat"
K_WINNING_TILE = "mj_winning_tile_id"
K_ROUND_WIND = "mj_round_wind"
K_HAND_NUMBER = "mj_hand_number"
K_RULESET = "mj_ruleset"


class AbstractMahjongGame:
    def __init__(
        self,
        ruleset: Ruleset,
        player_names: list[str],
        round_wind: int = 1,
        hand_number: int = 1,
    ) -> None:
        if len(player_names) != ruleset.seats:
            raise ValueError(
                f"need {ruleset.seats} players for this ruleset, got {len(player_names)}"
            )
        self.ruleset = ruleset
        self.player_names = player_names
        self.round_wind = round_wind
        self.hand_number = hand_number

    # ---- GameDef ----------------------------------------------------------
    def setup(self, state: GameState) -> list[Event]:
        rs = self.ruleset
        state.attrs[K_RULESET] = rs
        state.attrs[K_ROUND_WIND] = self.round_wind
        state.attrs[K_HAND_NUMBER] = self.hand_number

        for i, name in enumerate(self.player_names):
            p = Player(id=i, name=name)
            p.zones["hand"] = Zone("hand", Visibility.OWNER_ONLY, Ordering.UNORDERED, owner=i)
            p.zones["melds"] = Zone("melds", Visibility.PUBLIC, Ordering.ORDERED, owner=i)
            p.zones["discards"] = Zone("discards", Visibility.PUBLIC, Ordering.ORDERED, owner=i)
            p.resources["points"] = Resource("points", value=0)
            state.players[i] = p

        tiles = rs.build_wall_tiles()
        state.rng.shuffle(tiles)
        wall = Zone("wall", Visibility.HIDDEN, Ordering.ORDERED)
        for t in tiles:
            wall.push(t)
        state.zones["wall"] = wall

        dead = Zone("dead_wall", Visibility.HIDDEN, Ordering.ORDERED)
        for _ in range(rs.dead_wall_size):
            dead.push(wall.pop(0))
        state.zones["dead_wall"] = dead

        for _ in range(rs.initial_hand_size):
            for seat in range(rs.seats):
                state.players[seat].zones["hand"].push(wall.pop(0))

        dealer = rs.initial_dealer()
        state.attrs[K_CURRENT] = dealer
        state.phase = "hand"

        # dealer's opening draw
        drawn = self._draw_for(state, dealer)
        state.attrs[K_PHASE] = PHASE_AFTER_DRAW

        setup_events: list[Event] = [
            HandStarted(dealer=dealer, round_wind=self.round_wind, hand_number=self.hand_number),
            TileDrawn(seat=dealer, tile_id=drawn),
        ]
        for e in setup_events:
            rs.observe(state, e)
        return setup_events

    def decision_point(self, state: GameState) -> DecisionPoint | None:
        phase = state.attrs.get(K_PHASE)
        if phase == PHASE_END:
            return None
        rs = self.ruleset
        if phase == PHASE_AFTER_DRAW:
            seat = cast(PlayerId, state.attrs[K_CURRENT])
            legal = rs.legal_after_draw(state, seat, cast(int, state.attrs[K_LAST_DRAWN_TILE]))
            return DecisionPoint({seat: legal})
        if phase == PHASE_AFTER_CALL:
            seat = cast(PlayerId, state.attrs[K_CURRENT])
            legal = rs.legal_after_call(state, seat)
            return DecisionPoint({seat: legal})
        if phase == PHASE_RESPONSE:
            d_seat = cast(PlayerId, state.attrs[K_LAST_DISCARD_SEAT])
            t_id = cast(int, state.attrs[K_LAST_DISCARD_TILE])
            return DecisionPoint(rs.legal_responses(state, d_seat, t_id))
        raise RuntimeError(f"unknown phase: {phase}")

    def apply(self, state: GameState, decisions: dict[PlayerId, Action]) -> list[Event]:
        phase = state.attrs[K_PHASE]
        if phase == PHASE_AFTER_DRAW:
            events = self._apply_after_draw(state, decisions)
        elif phase == PHASE_AFTER_CALL:
            events = self._apply_after_call(state, decisions)
        elif phase == PHASE_RESPONSE:
            events = self._apply_response(state, decisions)
        else:
            raise RuntimeError(f"unexpected phase in apply: {phase}")
        for e in events:
            self.ruleset.observe(state, e)
        return events

    def is_terminal(self, state: GameState) -> bool:
        return state.attrs.get(K_PHASE) == PHASE_END

    def winners(self, state: GameState) -> list[PlayerId]:
        if state.attrs.get(K_RESULT) == "win":
            return [cast(PlayerId, state.attrs[K_WINNER])]
        return []

    # ---- phase handlers ---------------------------------------------------
    def _apply_after_draw(
        self, state: GameState, decisions: dict[PlayerId, Action]
    ) -> list[Event]:
        seat, action = next(iter(decisions.items()))

        if isinstance(action, DiscardAction):
            return self._do_discard(state, seat, action.tile_id)

        if isinstance(action, DeclareWinAction) and action.kind == "tsumo":
            return self._do_win(
                state,
                winner_seat=seat,
                loser_seat=None,
                winning_tile_id=cast(int, state.attrs[K_LAST_DRAWN_TILE]),
            )

        if isinstance(action, KanAction):
            evs = self._do_kan_from_hand(state, seat, action)
            drawn = self._draw_for(state, seat, from_dead_wall=True)
            evs.append(TileDrawn(seat=seat, tile_id=drawn, from_dead_wall=True))
            state.attrs[K_PHASE] = PHASE_AFTER_DRAW
            return evs

        if isinstance(action, DeclareRiichiAction):
            self.ruleset.apply_riichi(state, seat)
            self._do_discard(state, seat, action.discard_tile_id)
            return [
                RiichiDeclared(seat=seat),
                TileDiscarded(seat=seat, tile_id=action.discard_tile_id, riichi=True),
            ]

        raise RuntimeError(f"unhandled action in after_draw: {action!r}")

    def _apply_after_call(
        self, state: GameState, decisions: dict[PlayerId, Action]
    ) -> list[Event]:
        seat, action = next(iter(decisions.items()))
        if isinstance(action, DiscardAction):
            return self._do_discard(state, seat, action.tile_id)
        raise RuntimeError(f"unhandled after_call action: {action!r}")

    def _apply_response(
        self, state: GameState, decisions: dict[PlayerId, Action]
    ) -> list[Event]:
        rs = self.ruleset
        winning = rs.resolve_response_priority(state, decisions)
        if winning is None:
            return self._advance_to_next_draw(state)

        caller_seat, action = winning
        last_seat = cast(PlayerId, state.attrs[K_LAST_DISCARD_SEAT])
        last_tile_id = cast(int, state.attrs[K_LAST_DISCARD_TILE])
        called_tile = self._tile_by_id(state, last_tile_id)

        if isinstance(action, DeclareWinAction) and action.kind == "ron":
            return self._do_win(state, caller_seat, last_seat, last_tile_id)
        if isinstance(action, PonAction):
            return self._do_call_pair(state, caller_seat, action, last_seat, called_tile, PON)
        if isinstance(action, KanAction) and action.kind == MINKAN:
            return self._do_call_minkan(state, caller_seat, action, last_seat, called_tile)
        if isinstance(action, ChiAction):
            return self._do_call_pair(state, caller_seat, action, last_seat, called_tile, CHI)
        raise RuntimeError(f"unhandled response action: {action!r}")

    # ---- primitives -------------------------------------------------------
    def _draw_for(
        self, state: GameState, seat: PlayerId, from_dead_wall: bool = False
    ) -> int:
        source = state.zones["dead_wall"] if from_dead_wall else state.zones["wall"]
        tile = source.pop(0)
        state.players[seat].zones["hand"].push(tile)
        state.attrs[K_LAST_DRAWN_TILE] = tile.id
        return tile.id

    def _do_discard(self, state: GameState, seat: PlayerId, tile_id: int) -> list[Event]:
        p = state.players[seat]
        tile = self._find_tile_in_zone(p.zones["hand"], tile_id)
        p.zones["hand"].remove(tile)
        p.zones["discards"].push(tile)
        state.attrs[K_LAST_DISCARD_TILE] = tile_id
        state.attrs[K_LAST_DISCARD_SEAT] = seat
        state.attrs[K_PHASE] = PHASE_RESPONSE
        return [TileDiscarded(seat=seat, tile_id=tile_id)]

    def _do_win(
        self,
        state: GameState,
        winner_seat: PlayerId,
        loser_seat: PlayerId | None,
        winning_tile_id: int,
    ) -> list[Event]:
        rs = self.ruleset
        winning_tile = self._tile_by_id(state, winning_tile_id)
        deltas = rs.score_win(state, winner_seat, loser_seat, winning_tile)
        for seat, d in deltas.items():
            state.players[seat].resources["points"].adjust(d)
        state.attrs[K_PHASE] = PHASE_END
        state.attrs[K_RESULT] = "win"
        state.attrs[K_WINNER] = winner_seat
        state.attrs[K_WINNING_TILE] = winning_tile_id
        return [
            HandWon(
                winner=winner_seat,
                loser=loser_seat,
                winning_tile_id=winning_tile_id,
                score=deltas.get(winner_seat, 0),
            )
        ]

    def _do_kan_from_hand(
        self, state: GameState, seat: PlayerId, action: KanAction
    ) -> list[Event]:
        p = state.players[seat]
        if action.kind == ANKAN:
            tiles = [self._find_tile_in_zone(p.zones["hand"], tid) for tid in action.hand_tile_ids]
            for t in tiles:
                p.zones["hand"].remove(t)
            meld = Meld(ANKAN, tuple(tiles))
            p.zones["melds"].push(meld)
            return [MeldFormed(seat=seat, meld_id=meld.id, meld_type=ANKAN, called_from=None)]

        if action.kind == SHOUMINKAN:
            new_tile_id = action.hand_tile_ids[0]
            new_tile = self._find_tile_in_zone(p.zones["hand"], new_tile_id)
            p.zones["hand"].remove(new_tile)
            target = None
            for m in p.zones["melds"].items:
                if isinstance(m, Meld) and m.meld_type == PON and m.tiles[0].code == new_tile.code:
                    target = m
                    break
            if target is None:
                raise RuntimeError("shouminkan without matching pon")
            new_meld = Meld(
                SHOUMINKAN,
                target.tiles + (new_tile,),
                called_from=target.called_from,
                called_tile_id=target.called_tile_id,
            )
            idx = p.zones["melds"].items.index(target)
            p.zones["melds"].items[idx] = new_meld
            return [
                MeldFormed(
                    seat=seat,
                    meld_id=new_meld.id,
                    meld_type=SHOUMINKAN,
                    called_from=target.called_from,
                )
            ]

        raise RuntimeError(f"unsupported kan kind from hand: {action.kind}")

    def _do_call_pair(
        self,
        state: GameState,
        caller_seat: PlayerId,
        action: PonAction | ChiAction,
        last_seat: PlayerId,
        called_tile: Tile,
        meld_type: str,
    ) -> list[Event]:
        p = state.players[caller_seat]
        state.players[last_seat].zones["discards"].remove(called_tile)
        tiles_in_hand = [self._find_tile_in_zone(p.zones["hand"], tid) for tid in action.hand_tile_ids]
        for t in tiles_in_hand:
            p.zones["hand"].remove(t)
        meld = Meld(
            meld_type,
            tuple(tiles_in_hand + [called_tile]),
            called_from=last_seat,
            called_tile_id=called_tile.id,
        )
        p.zones["melds"].push(meld)
        state.attrs[K_CURRENT] = caller_seat
        state.attrs[K_PHASE] = PHASE_AFTER_CALL
        return [
            MeldFormed(seat=caller_seat, meld_id=meld.id, meld_type=meld_type, called_from=last_seat)
        ]

    def _do_call_minkan(
        self,
        state: GameState,
        caller_seat: PlayerId,
        action: KanAction,
        last_seat: PlayerId,
        called_tile: Tile,
    ) -> list[Event]:
        p = state.players[caller_seat]
        state.players[last_seat].zones["discards"].remove(called_tile)
        tiles_in_hand = [self._find_tile_in_zone(p.zones["hand"], tid) for tid in action.hand_tile_ids]
        for t in tiles_in_hand:
            p.zones["hand"].remove(t)
        meld = Meld(
            MINKAN,
            tuple(tiles_in_hand + [called_tile]),
            called_from=last_seat,
            called_tile_id=called_tile.id,
        )
        p.zones["melds"].push(meld)
        state.attrs[K_CURRENT] = caller_seat
        drawn = self._draw_for(state, caller_seat, from_dead_wall=True)
        state.attrs[K_PHASE] = PHASE_AFTER_DRAW
        return [
            MeldFormed(seat=caller_seat, meld_id=meld.id, meld_type=MINKAN, called_from=last_seat),
            TileDrawn(seat=caller_seat, tile_id=drawn, from_dead_wall=True),
        ]

    def _advance_to_next_draw(self, state: GameState) -> list[Event]:
        if state.zones["wall"].is_empty():
            state.attrs[K_PHASE] = PHASE_END
            state.attrs[K_RESULT] = "drawn"
            return [HandDrawn(tenpai_seats=())]
        cur = cast(PlayerId, state.attrs[K_CURRENT])
        nxt = (cur + 1) % self.ruleset.seats
        state.attrs[K_CURRENT] = nxt
        drawn = self._draw_for(state, nxt)
        state.attrs[K_PHASE] = PHASE_AFTER_DRAW
        return [TileDrawn(seat=nxt, tile_id=drawn)]

    # ---- lookups ----------------------------------------------------------
    def _find_tile_in_zone(self, zone: Zone, tile_id: int) -> Tile:
        for t in zone.items:
            if t.id == tile_id:
                return cast(Tile, t)
        raise KeyError(f"tile {tile_id} not in zone {zone.name}")

    def _tile_by_id(self, state: GameState, tile_id: int) -> Tile:
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
        raise KeyError(f"tile {tile_id} not found in state")
