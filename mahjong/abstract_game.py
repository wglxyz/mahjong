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
    DeclareAbortAction,
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
PHASE_CHANKAN = "chankan"          # waiting for chankan ron on a shouminkan upgrade
PHASE_HAND_END = "hand_end"        # current hand is over but match continues
PHASE_END = "match_end"            # whole match is over (engine treats as terminal)

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
K_CHANKAN_SEAT = "mj_chankan_seat"
K_CHANKAN_TILE_ID = "mj_chankan_tile_id"
K_DEALER_SEAT = "mj_dealer_seat"
K_HONBA = "mj_honba"
K_RIICHI_STICKS_POOL = "mj_riichi_sticks"
K_HAND_RESULTS = "mj_hand_results"


class AbstractMahjongGame:
    """Match orchestrator: multi-hand-aware. Common defaults match Japanese-style
    half-east tournament play; pass constructor args to deviate.

    Args:
      ruleset             — concrete dialect implementation
      player_names        — display names, one per seat (count must match ruleset.seats)
      rounds_per_match    — 1=東風戦, 2=半庄戦 (default; the most-played mode)
      initial_points      — starting score per seat (25000 is the modern standard)
      tenpai_renchan      — drawn-game dealer-tenpai → renchan (standard true)
    """

    def __init__(
        self,
        ruleset: Ruleset,
        player_names: list[str],
        round_wind: int = 1,
        hand_number: int = 1,
        rounds_per_match: int = 2,
        initial_points: int = 25000,
        tenpai_renchan: bool = True,
    ) -> None:
        if len(player_names) != ruleset.seats:
            raise ValueError(
                f"need {ruleset.seats} players for this ruleset, got {len(player_names)}"
            )
        self.ruleset = ruleset
        self.player_names = player_names
        self.starting_round_wind = round_wind
        self.starting_hand_number = hand_number
        self.rounds_per_match = rounds_per_match
        self.initial_points = initial_points
        self.tenpai_renchan = tenpai_renchan

    # ---- GameDef ----------------------------------------------------------
    def setup(self, state: GameState) -> list[Event]:
        rs = self.ruleset
        state.attrs[K_RULESET] = rs
        state.attrs[K_ROUND_WIND] = self.starting_round_wind
        state.attrs[K_HAND_NUMBER] = self.starting_hand_number
        state.attrs[K_DEALER_SEAT] = rs.initial_dealer()
        state.attrs[K_HONBA] = 0
        state.attrs[K_RIICHI_STICKS_POOL] = 0
        state.attrs[K_HAND_RESULTS] = []

        # match-level state: players persist across hands with cumulative points
        for i, name in enumerate(self.player_names):
            p = Player(id=i, name=name)
            p.zones["hand"] = Zone("hand", Visibility.OWNER_ONLY, Ordering.UNORDERED, owner=i)
            p.zones["melds"] = Zone("melds", Visibility.PUBLIC, Ordering.ORDERED, owner=i)
            p.zones["discards"] = Zone("discards", Visibility.PUBLIC, Ordering.ORDERED, owner=i)
            p.resources["points"] = Resource("points", value=self.initial_points)
            state.players[i] = p

        state.phase = "hand"
        return self._deal_new_hand(state)

    def _deal_new_hand(self, state: GameState) -> list[Event]:
        rs = self.ruleset
        # clear per-hand state
        for key in (
            K_RESULT, K_WINNER, K_WINNING_TILE,
            K_LAST_DRAWN_TILE, K_LAST_DISCARD_TILE, K_LAST_DISCARD_SEAT,
            K_CHANKAN_SEAT, K_CHANKAN_TILE_ID,
            "mj_any_call_yet", "mj_first_discards", "mj_abort_reason",
            "mj_last_yaku", "mj_last_han", "mj_last_fu", "mj_last_base",
            "mj_winners", "mj_winner_details", "mj_is_chankan_win",
        ):
            state.attrs.pop(key, None)

        # clear per-hand zones and per-player flags
        for p in state.players.values():
            p.zones["hand"].items.clear()
            p.zones["melds"].items.clear()
            p.zones["discards"].items.clear()
            # keep points; drop everything else
            p.attrs.clear()

        # rebuild wall, dead wall, dora indicators
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

        if "dora_indicators" in state.zones:
            state.zones["dora_indicators"].items.clear()

        # deal initial hands
        for _ in range(rs.initial_hand_size):
            for seat in range(rs.seats):
                state.players[seat].zones["hand"].push(wall.pop(0))

        dealer = cast(PlayerId, state.attrs[K_DEALER_SEAT])
        state.attrs[K_CURRENT] = dealer

        drawn = self._draw_for(state, dealer)
        state.attrs[K_PHASE] = PHASE_AFTER_DRAW

        events: list[Event] = [
            HandStarted(
                dealer=dealer,
                round_wind=cast(int, state.attrs[K_ROUND_WIND]),
                hand_number=cast(int, state.attrs[K_HAND_NUMBER]),
            ),
            TileDrawn(seat=dealer, tile_id=drawn),
        ]
        for e in events:
            rs.observe(state, e)
        return events

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
        if phase == PHASE_CHANKAN:
            k_seat = cast(PlayerId, state.attrs[K_CHANKAN_SEAT])
            t_id = cast(int, state.attrs[K_CHANKAN_TILE_ID])
            return DecisionPoint(rs.legal_responses(state, k_seat, t_id))
        raise RuntimeError(f"unknown phase: {phase}")

    def apply(self, state: GameState, decisions: dict[PlayerId, Action]) -> list[Event]:
        phase = state.attrs[K_PHASE]
        if phase == PHASE_AFTER_DRAW:
            events = self._apply_after_draw(state, decisions)
        elif phase == PHASE_AFTER_CALL:
            events = self._apply_after_call(state, decisions)
        elif phase == PHASE_RESPONSE:
            events = self._apply_response(state, decisions)
        elif phase == PHASE_CHANKAN:
            events = self._apply_chankan(state, decisions)
        else:
            raise RuntimeError(f"unexpected phase in apply: {phase}")
        for e in events:
            self.ruleset.observe(state, e)

        cur_phase = state.attrs.get(K_PHASE)

        # automatic abort check (4 winds, 4 kans, 4 riichi, …). Skip if hand already ended.
        if cur_phase not in (PHASE_HAND_END, PHASE_END):
            reason = self.ruleset.check_abort_conditions(state)
            if reason:
                state.attrs[K_PHASE] = PHASE_HAND_END
                state.attrs[K_RESULT] = "drawn"
                state.attrs["mj_abort_reason"] = reason
                # apply any drawn-game payouts
                deltas = self.ruleset.score_draw(state)
                for s, d in deltas.items():
                    if d:
                        state.players[s].resources["points"].adjust(d)
                drawn = HandDrawn(tenpai_seats=tuple(self.ruleset.seats_in_tenpai(state)))
                events.append(drawn)
                self.ruleset.observe(state, drawn)
                cur_phase = PHASE_HAND_END

        # hand → next-hand or match-end transition
        if cur_phase == PHASE_HAND_END:
            transition_events = self._advance_hand_or_end_match(state)
            for e in transition_events:
                self.ruleset.observe(state, e)
            events.extend(transition_events)
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
            if action.kind == SHOUMINKAN:
                # opponents may chankan-ron on the added tile before we draw rinshan
                state.attrs[K_CHANKAN_SEAT] = seat
                state.attrs[K_CHANKAN_TILE_ID] = action.hand_tile_ids[0]
                state.attrs[K_PHASE] = PHASE_CHANKAN
                return evs
            # ankan: no chankan window (with the rare exception of kokushi-chankan in some
            # rulesets — not modelled). Draw rinshan and continue.
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

        if isinstance(action, DeclareAbortAction):
            state.attrs[K_PHASE] = PHASE_HAND_END
            state.attrs[K_RESULT] = "drawn"
            state.attrs["mj_abort_reason"] = action.reason
            return [HandDrawn(tenpai_seats=())]

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
        winners = rs.resolve_response_priority(state, decisions)
        if winners is None:
            return self._advance_to_next_draw(state)
        if winners == []:
            # ruleset signalled an abort (e.g. triple ron). Treat as a drawn hand.
            state.attrs[K_PHASE] = PHASE_HAND_END
            state.attrs[K_RESULT] = "drawn"
            return [HandDrawn(tenpai_seats=())]

        last_seat = cast(PlayerId, state.attrs[K_LAST_DISCARD_SEAT])
        last_tile_id = cast(int, state.attrs[K_LAST_DISCARD_TILE])
        called_tile = self._tile_by_id(state, last_tile_id)

        # Multi-winner is only meaningful for ron. For everything else, take the first.
        if all(isinstance(a, DeclareWinAction) and a.kind == "ron" for _, a in winners):
            return self._do_multi_ron(state, [s for s, _ in winners], last_seat, last_tile_id)

        caller_seat, action = winners[0]
        if isinstance(action, DeclareWinAction) and action.kind == "ron":
            return self._do_win(state, caller_seat, last_seat, last_tile_id)
        if isinstance(action, PonAction):
            return self._do_call_pair(state, caller_seat, action, last_seat, called_tile, PON)
        if isinstance(action, KanAction) and action.kind == MINKAN:
            return self._do_call_minkan(state, caller_seat, action, last_seat, called_tile)
        if isinstance(action, ChiAction):
            return self._do_call_pair(state, caller_seat, action, last_seat, called_tile, CHI)
        raise RuntimeError(f"unhandled response action: {action!r}")

    def _advance_hand_or_end_match(self, state: GameState) -> list[Event]:
        """Decide what happens after a hand ends: deal a new hand, or terminate the match.

        Also: pays out the riichi stick pool to the closest winner (kept across drawn
        hands). Records a summary into state.attrs[K_HAND_RESULTS] before resetting.
        """
        rs = self.ruleset
        dealer = cast(int, state.attrs[K_DEALER_SEAT])
        result = cast(str, state.attrs.get(K_RESULT, "drawn"))
        winners: list[PlayerId] = list(state.attrs.get("mj_winners") or [])
        if not winners and state.attrs.get(K_WINNER) is not None:
            winners = [cast(PlayerId, state.attrs[K_WINNER])]

        # riichi-stick pool payout: closest winner (head-bumped) takes everything
        pool = cast(int, state.attrs.get(K_RIICHI_STICKS_POOL, 0))
        if result == "win" and winners and pool:
            d_seat = cast(int, state.attrs.get(K_LAST_DISCARD_SEAT, dealer))
            ordered = sorted(winners, key=lambda s: (s - d_seat) % rs.seats)
            recipient = ordered[0]
            state.players[recipient].resources["points"].adjust(pool * 1000)
            state.attrs[K_RIICHI_STICKS_POOL] = 0
        # drawn hand: pool carries into next hand (already tracked, do nothing)

        # record per-hand result snapshot
        hand_results = cast(list, state.attrs.setdefault(K_HAND_RESULTS, []))
        hand_results.append({
            "round_wind": state.attrs.get(K_ROUND_WIND),
            "hand_number": state.attrs.get(K_HAND_NUMBER),
            "honba": state.attrs.get(K_HONBA, 0),
            "dealer": dealer,
            "result": result,
            "winners": list(winners),
            "abort_reason": state.attrs.get("mj_abort_reason"),
            "points_after": {s: p.resources["points"].value for s, p in state.players.items()},
        })

        # decide renchan vs rotation
        dealer_won = dealer in winners
        dealer_tenpai_on_draw = False
        if result == "drawn" and self.tenpai_renchan:
            dealer_tenpai_on_draw = dealer in rs.seats_in_tenpai(state)
        renchan = dealer_won or dealer_tenpai_on_draw

        if renchan:
            state.attrs[K_HONBA] = cast(int, state.attrs.get(K_HONBA, 0)) + 1
            # dealer + hand_number + round_wind unchanged
        else:
            # bump honba on drawn-game rotation; reset on a non-dealer win
            if result == "drawn":
                state.attrs[K_HONBA] = cast(int, state.attrs.get(K_HONBA, 0)) + 1
            else:
                state.attrs[K_HONBA] = 0
            # rotate dealer
            new_dealer = (dealer + 1) % rs.seats
            state.attrs[K_DEALER_SEAT] = new_dealer
            new_hand = cast(int, state.attrs.get(K_HAND_NUMBER, 1)) + 1
            if new_hand > rs.seats:
                # round complete
                new_round = cast(int, state.attrs.get(K_ROUND_WIND, 1)) + 1
                if new_round > self.rounds_per_match:
                    state.attrs[K_PHASE] = PHASE_END
                    return []
                state.attrs[K_ROUND_WIND] = new_round
                state.attrs[K_HAND_NUMBER] = 1
            else:
                state.attrs[K_HAND_NUMBER] = new_hand

        # deal next hand
        return self._deal_new_hand(state)

    def _apply_chankan(
        self, state: GameState, decisions: dict[PlayerId, Action]
    ) -> list[Event]:
        rs = self.ruleset
        kanner = cast(PlayerId, state.attrs[K_CHANKAN_SEAT])
        added_tile_id = cast(int, state.attrs[K_CHANKAN_TILE_ID])
        winners = rs.resolve_response_priority(state, decisions)

        if winners is None or winners == []:
            # all passed (or weird abort signal) — proceed with the rinshan draw
            state.attrs.pop(K_CHANKAN_SEAT, None)
            state.attrs.pop(K_CHANKAN_TILE_ID, None)
            drawn = self._draw_for(state, kanner, from_dead_wall=True)
            state.attrs[K_PHASE] = PHASE_AFTER_DRAW
            return [TileDrawn(seat=kanner, tile_id=drawn, from_dead_wall=True)]

        # someone ron'd the added tile — chankan win
        state.attrs["mj_is_chankan_win"] = True
        try:
            if len(winners) == 1:
                w_seat, _ = winners[0]
                events = self._do_win(state, w_seat, kanner, added_tile_id)
            else:
                events = self._do_multi_ron(
                    state, [s for s, _ in winners], kanner, added_tile_id
                )
        finally:
            state.attrs.pop("mj_is_chankan_win", None)
            state.attrs.pop(K_CHANKAN_SEAT, None)
            state.attrs.pop(K_CHANKAN_TILE_ID, None)
        return events

    def _do_multi_ron(
        self,
        state: GameState,
        winner_seats: list[PlayerId],
        loser_seat: PlayerId,
        winning_tile_id: int,
    ) -> list[Event]:
        """Each winner is scored independently against the discarder; deltas sum across
        winners. Emits one HandWon per winner. Terminal state records the closest seat
        as the headline winner for legacy single-winner consumers."""
        winning_tile = self._tile_by_id(state, winning_tile_id)
        per_winner_yaku: list[tuple[PlayerId, dict[PlayerId, int], list, int, int]] = []
        total_deltas: dict[PlayerId, int] = {s: 0 for s in range(self.ruleset.seats)}

        for winner_seat in winner_seats:
            deltas = self.ruleset.score_win(state, winner_seat, loser_seat, winning_tile)
            yaku_list = list(state.attrs.get("mj_last_yaku", []))
            han = cast(int, state.attrs.get("mj_last_han", 0))
            fu = cast(int, state.attrs.get("mj_last_fu", 0))
            per_winner_yaku.append((winner_seat, deltas, yaku_list, han, fu))
            for s, d in deltas.items():
                total_deltas[s] += d

        # apply the summed deltas once
        for s, d in total_deltas.items():
            if d:
                state.players[s].resources["points"].adjust(d)

        state.attrs[K_PHASE] = PHASE_HAND_END
        state.attrs[K_RESULT] = "win"
        # for legacy single-winner consumers, record the first (closest to discarder)
        state.attrs[K_WINNER] = winner_seats[0]
        state.attrs[K_WINNING_TILE] = winning_tile_id
        state.attrs["mj_winners"] = list(winner_seats)
        state.attrs["mj_winner_details"] = [
            {"seat": s, "deltas": d, "yaku": y, "han": h, "fu": f}
            for s, d, y, h, f in per_winner_yaku
        ]

        events: list[Event] = []
        for winner_seat, deltas, _, _, _ in per_winner_yaku:
            events.append(
                HandWon(
                    winner=winner_seat,
                    loser=loser_seat,
                    winning_tile_id=winning_tile_id,
                    score=deltas.get(winner_seat, 0),
                )
            )
        return events

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
        state.attrs[K_PHASE] = PHASE_HAND_END
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
            state.attrs[K_PHASE] = PHASE_HAND_END
            state.attrs[K_RESULT] = "drawn"
            # let the ruleset apply any drawn-game payouts (nagashi mangan, tenpai penalty)
            deltas = self.ruleset.score_draw(state)
            for seat, d in deltas.items():
                if d:
                    state.players[seat].resources["points"].adjust(d)
            return [HandDrawn(tenpai_seats=tuple(self.ruleset.seats_in_tenpai(state)))]
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
