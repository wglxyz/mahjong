"""SimpleRuleset: the smallest mahjong dialect that exercises every L2 hook.

Design choices:
  - Tile set: 3 numeric suits (m/p/s) × 9 ranks × 4 copies = 108 tiles. No honors, flowers, red 5s.
  - 4 players, 13-tile hand, no dead wall.
  - Legal calls: pon and ron only. No chi, no kan, no riichi.
  - Win shape: 4 melds (sequences or triplets) + 1 pair. No yaku requirement.
  - Scoring: winner +3 points, losers -1 each (tsumo) or loser -3 (ron). Zero-sum.

It is intentionally bare; the point is to verify AbstractMahjongGame wires up correctly.
"""
from __future__ import annotations
from typing import cast

from core.action import Action
from core.player import PlayerId
from core.state import GameState
from mahjong.actions import (
    DeclareWinAction,
    DiscardAction,
    PassAction,
    PonAction,
)
from mahjong.meld import Meld
from mahjong.tile import NUMERIC_SUITS, SUIT_M, SUIT_P, SUIT_S, Tile


class SimpleRuleset:
    seats = 4
    initial_hand_size = 13
    dead_wall_size = 0

    # ---- wall --------------------------------------------------------------
    def build_wall_tiles(self) -> list[Tile]:
        tiles: list[Tile] = []
        for suit in (SUIT_M, SUIT_P, SUIT_S):
            for rank in range(1, 10):
                for _ in range(4):
                    tiles.append(Tile(suit, rank))
        return tiles

    def initial_dealer(self) -> PlayerId:
        return 0

    # ---- decision points --------------------------------------------------
    def legal_after_draw(
        self, state: GameState, seat: PlayerId, drawn_tile_id: int
    ) -> list[Action]:
        p = state.players[seat]
        hand = [cast(Tile, t) for t in p.zones["hand"].items]
        melds = [cast(Meld, m) for m in p.zones["melds"].items]

        # one Discard per *unique tile code* — avoids generating 14 nearly-identical actions
        # when the hand has duplicates. We just take the first tile of each code.
        seen: dict[str, int] = {}
        actions: list[Action] = []
        for t in hand:
            if t.code not in seen:
                seen[t.code] = t.id
                actions.append(DiscardAction(actor=seat, tile_id=t.id))

        drawn_tile = next(t for t in hand if t.id == drawn_tile_id)
        if self.is_winning_hand(hand, melds, drawn_tile, {}):
            actions.append(DeclareWinAction(actor=seat, kind="tsumo"))
        return actions

    def legal_after_call(self, state: GameState, seat: PlayerId) -> list[Action]:
        p = state.players[seat]
        hand = [cast(Tile, t) for t in p.zones["hand"].items]
        seen: dict[str, int] = {}
        actions: list[Action] = []
        for t in hand:
            if t.code not in seen:
                seen[t.code] = t.id
                actions.append(DiscardAction(actor=seat, tile_id=t.id))
        return actions

    def legal_responses(
        self, state: GameState, discard_seat: PlayerId, discarded_tile_id: int
    ) -> dict[PlayerId, list[Action]]:
        # find the discarded tile
        discards = state.players[discard_seat].zones["discards"]
        discarded_tile = next(
            cast(Tile, t) for t in discards.items if t.id == discarded_tile_id
        )

        out: dict[PlayerId, list[Action]] = {}
        for seat in range(self.seats):
            if seat == discard_seat:
                continue
            p = state.players[seat]
            hand = [cast(Tile, t) for t in p.zones["hand"].items]
            melds = [cast(Meld, m) for m in p.zones["melds"].items]

            legal: list[Action] = [PassAction(actor=seat)]

            # ron — hand + discarded_tile completes a winning shape
            if self.is_winning_hand(hand + [discarded_tile], melds, discarded_tile, {}):
                legal.append(DeclareWinAction(actor=seat, kind="ron"))

            # pon — hand contains two tiles with same code as discard
            same = [t for t in hand if t.code == discarded_tile.code]
            if len(same) >= 2:
                legal.append(
                    PonAction(actor=seat, hand_tile_ids=(same[0].id, same[1].id))
                )

            out[seat] = legal
        return out

    def resolve_response_priority(
        self, state: GameState, decisions: dict[PlayerId, Action]
    ) -> list[tuple[PlayerId, Action]] | None:
        # SimpleRuleset is single-winner: head-bump for ron, no double-ron, no abort.
        rons = [(s, a) for s, a in decisions.items() if isinstance(a, DeclareWinAction)]
        if rons:
            d_seat = cast(PlayerId, state.attrs["mj_last_discard_seat"])
            rons.sort(key=lambda sa: (sa[0] - d_seat) % self.seats)
            return [rons[0]]
        pons = [(s, a) for s, a in decisions.items() if isinstance(a, PonAction)]
        if pons:
            return [pons[0]]
        return None

    # ---- win detection ----------------------------------------------------
    def is_winning_hand(
        self,
        hand_tiles: list[Tile],
        melds: list[Meld],
        winning_tile: Tile,
        context: dict,
    ) -> bool:
        needed = 4 - len(melds)
        if needed < 0:
            return False
        expected = needed * 3 + 2
        if len(hand_tiles) != expected:
            return False
        counts: dict[str, int] = {}
        for t in hand_tiles:
            counts[t.code] = counts.get(t.code, 0) + 1
        for k in list(counts.keys()):
            if counts[k] >= 2:
                counts[k] -= 2
                if _can_form_n_melds(counts, needed):
                    counts[k] += 2
                    return True
                counts[k] += 2
        return False

    # ---- side-effect hooks (no-ops for this simplified dialect) -----------
    def apply_riichi(self, state: GameState, seat: PlayerId) -> None:
        # SimpleRuleset doesn't model riichi; the abstract game never emits a riichi action
        # because legal_after_draw never includes DeclareRiichiAction.
        return None

    def observe(self, state: GameState, event) -> None:
        return None

    def score_draw(self, state: GameState) -> dict[PlayerId, int]:
        # SimpleRuleset has no special drawn-game payouts.
        return {s: 0 for s in range(self.seats)}

    def check_abort_conditions(self, state: GameState) -> str | None:
        return None

    def seats_in_tenpai(self, state: GameState) -> list[PlayerId]:
        return []

    # ---- scoring ----------------------------------------------------------
    def score_win(
        self,
        state: GameState,
        winner_seat: PlayerId,
        loser_seat: PlayerId | None,
        winning_tile: Tile,
    ) -> dict[PlayerId, int]:
        deltas: dict[PlayerId, int] = {s: 0 for s in range(self.seats)}
        if loser_seat is None:
            # tsumo
            deltas[winner_seat] = 3
            for s in range(self.seats):
                if s != winner_seat:
                    deltas[s] = -1
        else:
            deltas[winner_seat] = 3
            deltas[loser_seat] = -3
        return deltas


# ---- helpers --------------------------------------------------------------
def _can_form_n_melds(counts: dict[str, int], n: int) -> bool:
    if n == 0:
        return all(v == 0 for v in counts.values())
    keys = sorted(k for k, v in counts.items() if v > 0)
    if not keys:
        return False
    k = keys[0]
    suit = k[0]
    rank = int(k[1:])

    # triplet
    if counts[k] >= 3:
        counts[k] -= 3
        if _can_form_n_melds(counts, n - 1):
            counts[k] += 3
            return True
        counts[k] += 3

    # sequence
    if suit in NUMERIC_SUITS and rank <= 7:
        k2 = f"{suit}{rank + 1}"
        k3 = f"{suit}{rank + 2}"
        if counts.get(k2, 0) >= 1 and counts.get(k3, 0) >= 1:
            counts[k] -= 1
            counts[k2] -= 1
            counts[k3] -= 1
            if _can_form_n_melds(counts, n - 1):
                counts[k] += 1
                counts[k2] += 1
                counts[k3] += 1
                return True
            counts[k] += 1
            counts[k2] += 1
            counts[k3] += 1

    return False
