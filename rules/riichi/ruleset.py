"""RiichiRuleset — assembles the Riichi mahjong dialect.

Implements the mahjong.ruleset.Ruleset protocol. Delegates:
  - tile-set construction → tileset.py
  - hand decomposition    → decompose.py
  - yaku detection        → yaku.py
  - point computation     → score.py

State this ruleset maintains via player.attrs and state.attrs (set via observe()):
  - player.attrs["riichi"]            : riichi declared
  - player.attrs["double_riichi"]     : declared on first turn with no calls
  - player.attrs["ippatsu"]           : ippatsu eligibility window open
  - player.attrs["ippatsu_skip_one"]  : skip the riichi-discard itself when expiring
  - player.attrs["draw_count"]        : draws taken this hand (for first-turn yaku)
  - state.attrs["mj_rinshan_pending"] : last draw was from dead wall (kan replacement)
  - state.attrs["mj_dealer_seat"]     : seat of the current dealer
  - state.attrs["mj_any_call_yet"]    : True after first MeldFormed (kills tenhou/chiihou)
  - state.attrs["mj_first_discards"]  : list of (seat, code) for first-round abort check
  - state.attrs["mj_abort_reason"]    : tag set when an abort fires

Known remaining simplifications (see TODO.md for the full list):
  - Permanent furiten only — no temporary (skipped-ron) furiten
  - No tenpai/noten penalty at exhaustive drawn game
  - Single-hand session (no East-round rotation; that lives at the Session layer)
"""
from __future__ import annotations
from typing import cast

from core.action import Action
from core.player import PlayerId
from core.state import GameState
from core.zone import Ordering, Visibility, Zone
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
from mahjong.events import HandStarted, MeldFormed, TileDiscarded, TileDrawn
from mahjong.meld import ANKAN, MINKAN, PON, SHOUMINKAN, Meld
from mahjong.tile import NUMERIC_SUITS, SUIT_Z, Tile

from rules.riichi.decompose import all_decompositions
from rules.riichi.score import score as score_calc
from rules.riichi.tileset import build_riichi_wall, dora_from_indicator
from rules.riichi.yaku import YakuContext, evaluate


# ---- helpers ---------------------------------------------------------------
def _is_concealed_hand(player) -> bool:
    """A hand is 'concealed' for yaku/riichi/scoring iff no open meld exists.
    Ankan keeps concealment."""
    for m in player.zones["melds"].items:
        if isinstance(m, Meld) and m.meld_type != ANKAN:
            return False
    return True


def _all_tile_codes() -> list[tuple[str, int]]:
    out = [(s, r) for s in NUMERIC_SUITS for r in range(1, 10)]
    out += [(SUIT_Z, r) for r in range(1, 8)]
    return out


def _waiting_codes(concealed_tiles: list[Tile], declared_melds: list[Meld]) -> set[str]:
    """The set of tile codes that would complete the hand."""
    waits: set[str] = set()
    for suit, rank in _all_tile_codes():
        probe = Tile(suit, rank)
        if all_decompositions(concealed_tiles + [probe], declared_melds, probe):
            waits.add(f"{suit}{rank}")
    return waits


def _is_tenpai(concealed_tiles: list[Tile], declared_melds: list[Meld]) -> bool:
    """True iff any 1-tile addition would yield a winning shape."""
    return bool(_waiting_codes(concealed_tiles, declared_melds))


def _is_furiten(
    concealed_tiles: list[Tile],
    declared_melds: list[Meld],
    own_discards: list[Tile],
) -> bool:
    """Permanent furiten: at least one waiting tile sits in the player's own discard pile.

    Furiten disables ron entirely (tsumo is still allowed). Temporary furiten (skipped
    ron until next own draw) is not modelled.
    """
    waits = _waiting_codes(concealed_tiles, declared_melds)
    if not waits:
        return False
    return any(t.code in waits for t in own_discards)


def _count_dora(decomp_groups, indicators: list[Tile]) -> int:
    if not indicators:
        return 0
    dora_codes = set()
    for ind in indicators:
        suit, rank = dora_from_indicator(ind)
        dora_codes.add(f"{suit}{rank}")
    count = 0
    for g in decomp_groups:
        for t in g.tiles:
            if t in dora_codes:
                count += 1
    return count


def _count_red(concealed_tiles: list[Tile], declared_melds: list[Meld]) -> int:
    n = sum(1 for t in concealed_tiles if t.red)
    for m in declared_melds:
        n += sum(1 for t in m.tiles if t.red)
    return n


def _seat_wind(seat: PlayerId, dealer: PlayerId, seats: int = 4) -> int:
    """Returns wind index 1..4 for the given seat given the dealer's seat (East)."""
    return ((seat - dealer) % seats) + 1


def _is_terminal_or_honor(tile: Tile) -> bool:
    return tile.suit == SUIT_Z or (tile.suit in NUMERIC_SUITS and tile.rank in (1, 9))


def _find_tile_anywhere(state: GameState, tile_id: int) -> Tile | None:
    for z in state.zones.values():
        for it in z.items:
            if getattr(it, "id", None) == tile_id:
                return cast(Tile, it)
    for p in state.players.values():
        for z in p.zones.values():
            for it in z.items:
                if isinstance(it, Meld):
                    for tt in it.tiles:
                        if tt.id == tile_id:
                            return tt
                elif getattr(it, "id", None) == tile_id:
                    return cast(Tile, it)
    return None


# ---- ruleset ---------------------------------------------------------------
class RiichiRuleset:
    seats = 4
    initial_hand_size = 13
    dead_wall_size = 14
    use_red_fives = True

    # ---- wall ---------------------------------------------------------------
    def build_wall_tiles(self) -> list[Tile]:
        return build_riichi_wall(red_fives=self.use_red_fives)

    def initial_dealer(self) -> PlayerId:
        return 0

    # ---- decision points ----------------------------------------------------
    def legal_after_draw(
        self, state: GameState, seat: PlayerId, drawn_tile_id: int
    ) -> list[Action]:
        p = state.players[seat]
        hand = [cast(Tile, t) for t in p.zones["hand"].items]
        declared = [cast(Meld, m) for m in p.zones["melds"].items]
        drew = next(t for t in hand if t.id == drawn_tile_id)
        riichi_declared = bool(p.attrs.get("riichi"))

        actions: list[Action] = []

        # --- DECLARE WIN (tsumo) — only if hand wins AND has yaku ----------
        ctx = self._build_ctx(state, seat, winning_tile=drew, is_tsumo=True, declared=declared)
        decomps = all_decompositions(hand, declared, drew)
        if decomps:
            ctx.dora_count = _count_dora_for_best(decomps, ctx, state)
            ctx.red_dora_count = _count_red(hand, declared)
            yres = evaluate(decomps, ctx)
            if yres is not None:
                actions.append(DeclareWinAction(actor=seat, kind="tsumo"))

        # --- ANKAN / SHOUMINKAN ---------------------------------------------
        if not riichi_declared:    # we don't allow kans post-riichi (simplification)
            counts: dict[str, list[int]] = {}
            for t in hand:
                counts.setdefault(t.code, []).append(t.id)
            for code, ids in counts.items():
                if len(ids) == 4:
                    actions.append(
                        KanAction(actor=seat, kind=ANKAN, hand_tile_ids=tuple(ids))
                    )
            # shouminkan: drawn tile matches an existing pon
            for m in declared:
                if isinstance(m, Meld) and m.meld_type == PON:
                    if m.tiles[0].code == drew.code:
                        actions.append(
                            KanAction(
                                actor=seat,
                                kind=SHOUMINKAN,
                                hand_tile_ids=(drew.id,),
                            )
                        )

        # --- DISCARDS --------------------------------------------------------
        if riichi_declared:
            # post-riichi: tsumogiri only
            actions.append(DiscardAction(actor=seat, tile_id=drew.id))
        else:
            seen: set[str] = set()
            for t in hand:
                if t.code in seen:
                    continue
                seen.add(t.code)
                actions.append(DiscardAction(actor=seat, tile_id=t.id))

        # --- RIICHI ---------------------------------------------------------
        if (
            not riichi_declared
            and _is_concealed_hand(p)
            and p.resources["points"].value >= 1000
            and len(state.zones["wall"].items) >= 4
        ):
            # offer riichi for each discard that keeps tenpai
            seen_codes: set[str] = set()
            for t in hand:
                if t.code in seen_codes:
                    continue
                seen_codes.add(t.code)
                remaining = [x for x in hand if x.id != t.id]
                if _is_tenpai(remaining, declared):
                    actions.append(
                        DeclareRiichiAction(actor=seat, discard_tile_id=t.id)
                    )

        # --- NINE-TERMINALS abort -------------------------------------------
        # Offered only on this seat's first turn, with no calls intervening.
        is_first_turn = (
            not state.attrs.get("mj_any_call_yet")
            and p.attrs.get("draw_count", 0) == 1
        )
        if is_first_turn:
            unique_terminal_honor = {tt.code for tt in hand if _is_terminal_or_honor(tt)}
            if len(unique_terminal_honor) >= 9:
                actions.append(
                    DeclareAbortAction(actor=seat, reason="nine_terminals")
                )

        return actions

    def legal_after_call(self, state: GameState, seat: PlayerId) -> list[Action]:
        p = state.players[seat]
        hand = [cast(Tile, t) for t in p.zones["hand"].items]
        actions: list[Action] = []
        seen: set[str] = set()
        for t in hand:
            if t.code in seen:
                continue
            seen.add(t.code)
            actions.append(DiscardAction(actor=seat, tile_id=t.id))
        return actions

    def legal_responses(
        self, state: GameState, discard_seat: PlayerId, discarded_tile_id: int
    ) -> dict[PlayerId, list[Action]]:
        is_chankan = state.attrs.get("mj_phase") == "chankan"
        if is_chankan:
            # the "discarded" tile lives in the kanner's meld zone, not the discard pile
            d_tile = _find_tile_anywhere(state, discarded_tile_id)
            if d_tile is None:
                return {s: [PassAction(actor=s)] for s in range(self.seats) if s != discard_seat}
        else:
            discards = state.players[discard_seat].zones["discards"]
            d_tile = next(cast(Tile, t) for t in discards.items if t.id == discarded_tile_id)
        wall_empty = state.zones["wall"].is_empty()

        out: dict[PlayerId, list[Action]] = {}
        for seat in range(self.seats):
            if seat == discard_seat:
                continue
            p = state.players[seat]
            riichi = bool(p.attrs.get("riichi"))
            hand = [cast(Tile, t) for t in p.zones["hand"].items]
            declared = [cast(Meld, m) for m in p.zones["melds"].items]

            legal: list[Action] = [PassAction(actor=seat)]

            # --- RON ---------------------------------------------------------
            full_hand = hand + [d_tile]
            decomps = all_decompositions(full_hand, declared, d_tile)
            own_discards = [cast(Tile, t) for t in p.zones["discards"].items]
            if decomps and not _is_furiten(hand, declared, own_discards):
                ctx = self._build_ctx(state, seat, winning_tile=d_tile, is_tsumo=False, declared=declared)
                ctx.is_houtei = wall_empty
                if is_chankan:
                    ctx.is_chankan = True
                ctx.dora_count = _count_dora_for_best(decomps, ctx, state)
                ctx.red_dora_count = _count_red(hand, declared) + (1 if d_tile.red else 0)
                yres = evaluate(decomps, ctx)
                if yres is not None:
                    legal.append(DeclareWinAction(actor=seat, kind="ron"))

            if is_chankan or riichi:
                # in chankan mode only ron is allowed; riichi'd seats also can't call
                out[seat] = legal
                continue

            # --- PON ---------------------------------------------------------
            same = [t for t in hand if t.code == d_tile.code]
            if len(same) >= 2:
                legal.append(
                    PonAction(actor=seat, hand_tile_ids=(same[0].id, same[1].id))
                )

            # --- MINKAN ------------------------------------------------------
            if len(same) >= 3:
                legal.append(
                    KanAction(
                        actor=seat,
                        kind=MINKAN,
                        hand_tile_ids=tuple(t.id for t in same[:3]),
                    )
                )

            # --- CHI (left seat only) ----------------------------------------
            left = (discard_seat + 1) % self.seats
            if seat == left and d_tile.suit in NUMERIC_SUITS:
                r = d_tile.rank
                suit = d_tile.suit

                def has(rank: int) -> list[Tile]:
                    return [t for t in hand if t.suit == suit and t.rank == rank]

                # discard is low end (r r+1 r+2)
                if r <= 7:
                    a = has(r + 1)
                    b = has(r + 2)
                    if a and b:
                        legal.append(
                            ChiAction(actor=seat, hand_tile_ids=(a[0].id, b[0].id))
                        )
                # discard is middle (r-1 r r+1)
                if 2 <= r <= 8:
                    a = has(r - 1)
                    b = has(r + 1)
                    if a and b:
                        legal.append(
                            ChiAction(actor=seat, hand_tile_ids=(a[0].id, b[0].id))
                        )
                # discard is high end (r-2 r-1 r)
                if r >= 3:
                    a = has(r - 2)
                    b = has(r - 1)
                    if a and b:
                        legal.append(
                            ChiAction(actor=seat, hand_tile_ids=(a[0].id, b[0].id))
                        )

            out[seat] = legal
        return out

    def resolve_response_priority(
        self, state: GameState, decisions: dict[PlayerId, Action]
    ) -> list[tuple[PlayerId, Action]] | None:
        d_seat = cast(PlayerId, state.attrs["mj_last_discard_seat"])

        # ron beats everything. Triple-ron aborts the hand; double-ron splits.
        rons = [(s, a) for s, a in decisions.items() if isinstance(a, DeclareWinAction)]
        if rons:
            if len(rons) >= 3:
                state.attrs["mj_abort_reason"] = "triple_ron"
                return []
            rons.sort(key=lambda sa: (sa[0] - d_seat) % self.seats)
            return rons

        pons_kans = [
            (s, a)
            for s, a in decisions.items()
            if isinstance(a, (PonAction, KanAction))
        ]
        if pons_kans:
            return [pons_kans[0]]

        chis = [(s, a) for s, a in decisions.items() if isinstance(a, ChiAction)]
        if chis:
            return [chis[0]]

        return None

    # ---- win / score --------------------------------------------------------
    def is_winning_hand(
        self,
        hand_tiles: list[Tile],
        melds: list[Meld],
        winning_tile: Tile,
        context: dict,
    ) -> bool:
        """Cheap structural check used by tests. Doesn't validate yaku presence."""
        return bool(all_decompositions(hand_tiles, melds, winning_tile))

    def score_win(
        self,
        state: GameState,
        winner_seat: PlayerId,
        loser_seat: PlayerId | None,
        winning_tile: Tile,
    ) -> dict[PlayerId, int]:
        p = state.players[winner_seat]
        hand = [cast(Tile, t) for t in p.zones["hand"].items]
        declared = [cast(Meld, m) for m in p.zones["melds"].items]
        is_tsumo = loser_seat is None

        # For ron, hand currently does NOT include the winning tile (it's in the loser's discards).
        # Synthesise the full hand for decomposition.
        if is_tsumo:
            full_hand = hand
        else:
            full_hand = hand + [winning_tile]

        decomps = all_decompositions(full_hand, declared, winning_tile)
        if not decomps:
            # shouldn't happen — DeclareWinAction should only be offered when decomps exist
            return {s: 0 for s in range(self.seats)}

        ctx = self._build_ctx(state, winner_seat, winning_tile, is_tsumo, declared)
        wall_empty = state.zones["wall"].is_empty()
        if is_tsumo:
            ctx.is_haitei = wall_empty
        else:
            ctx.is_houtei = wall_empty
        ctx.dora_count = _count_dora_for_best(decomps, ctx, state)
        ctx.red_dora_count = _count_red(hand, declared) + (
            1 if (not is_tsumo and winning_tile.red) else 0
        )
        if ctx.is_riichi:
            ura = _peek_ura_indicators(state)
            ctx.ura_dora_count = _count_dora_with_indicators(decomps, ura)
        yres = evaluate(decomps, ctx)
        if yres is None:
            # yakuless win — abstract game shouldn't get here, but return no-op deltas
            return {s: 0 for s in range(self.seats)}

        dealer_seat = state.attrs.get("mj_dealer_seat", 0)
        deltas, _fu, _base = score_calc(
            yres,
            ctx,
            winner_seat=winner_seat,
            loser_seat=loser_seat,
            dealer_seat=cast(int, dealer_seat),
            seats=self.seats,
        )
        # store debug info on state for UIs to display
        state.attrs["mj_last_yaku"] = list(yres.yaku)
        state.attrs["mj_last_han"] = yres.total_han
        state.attrs["mj_last_fu"] = _fu
        state.attrs["mj_last_base"] = _base
        return deltas

    # ---- tenpai inspection -------------------------------------------------
    def seats_in_tenpai(self, state: GameState) -> list[PlayerId]:
        out: list[PlayerId] = []
        for seat, p in state.players.items():
            hand = [cast(Tile, t) for t in p.zones["hand"].items]
            declared = [cast(Meld, m) for m in p.zones["melds"].items]
            # tenpai shape requires (4 - melds) * 3 + 1 tiles in hand (13-tile state)
            expected = (4 - len(declared)) * 3 + 1
            if len(hand) != expected:
                continue
            if _is_tenpai(hand, declared):
                out.append(seat)
        return out

    # ---- automatic aborts --------------------------------------------------
    def check_abort_conditions(self, state: GameState) -> str | None:
        # 4-winds first-round discards (suufuurenta) — all 4 first discards are the same wind
        if not state.attrs.get("mj_any_call_yet"):
            fd = state.attrs.get("mj_first_discards", [])
            if len(fd) == self.seats:
                codes = {c for _, c in fd}
                if len(codes) == 1:
                    code = next(iter(codes))
                    if code.startswith("z") and 1 <= int(code[1:]) <= 4:
                        return "four_winds_first_discards"

        # 4 kans by ≥2 different players (suukaikan abort; one-player 4 kans = suukantsu yakuman)
        kan_seats: list[PlayerId] = []
        for s, p in state.players.items():
            for m in p.zones["melds"].items:
                if isinstance(m, Meld) and m.meld_type in (MINKAN, ANKAN, SHOUMINKAN):
                    kan_seats.append(s)
        if len(kan_seats) >= 4 and len(set(kan_seats)) >= 2:
            return "four_kans"

        # all 4 players have declared riichi
        if all(p.attrs.get("riichi") for p in state.players.values()):
            return "four_riichis"

        return None

    # ---- drawn-game scoring (nagashi mangan) -------------------------------
    def score_draw(self, state: GameState) -> dict[PlayerId, int]:
        deltas: dict[PlayerId, int] = {s: 0 for s in range(self.seats)}
        dealer = cast(int, state.attrs.get("mj_dealer_seat", 0))
        nagashi_seats = []
        for seat, p in state.players.items():
            disc = [cast(Tile, t) for t in p.zones["discards"].items]
            if not disc:
                continue
            if not all(_is_terminal_or_honor(t) for t in disc):
                continue
            # any opponent meld called from this seat fails nagashi
            called = False
            for op in state.players.values():
                for m in op.zones["melds"].items:
                    if isinstance(m, Meld) and m.called_from == seat:
                        called = True
                        break
                if called:
                    break
            if called:
                continue
            nagashi_seats.append(seat)

        # each qualifying seat is paid as a mangan-tsumo equivalent
        for ns in nagashi_seats:
            is_dealer_win = ns == dealer
            if is_dealer_win:
                # each non-dealer pays 4000 → winner +12000
                for s in range(self.seats):
                    if s == ns:
                        deltas[s] += 12000
                    else:
                        deltas[s] -= 4000
            else:
                # dealer pays 4000, each non-dealer pays 2000 → winner +8000
                for s in range(self.seats):
                    if s == ns:
                        deltas[s] += 8000
                    elif s == dealer:
                        deltas[s] -= 4000
                    else:
                        deltas[s] -= 2000
        state.attrs["mj_nagashi_seats"] = list(nagashi_seats)
        return deltas

    # ---- side-effect hooks --------------------------------------------------
    def apply_riichi(self, state: GameState, seat: PlayerId) -> None:
        p = state.players[seat]
        p.attrs["riichi"] = True
        p.attrs["ippatsu"] = True
        # the riichi declaration's discard should NOT immediately clear ippatsu
        p.attrs["ippatsu_skip_one"] = True
        # double riichi: declared on the seat's first turn, no calls have happened
        if (
            not state.attrs.get("mj_any_call_yet", False)
            and p.attrs.get("draw_count", 0) == 1
        ):
            p.attrs["double_riichi"] = True
        p.resources["points"].adjust(-1000)
        state.attrs["mj_riichi_sticks"] = state.attrs.get("mj_riichi_sticks", 0) + 1

    def observe(self, state: GameState, event) -> None:
        if isinstance(event, HandStarted):
            state.attrs["mj_dealer_seat"] = event.dealer
            state.attrs["mj_any_call_yet"] = False
            state.attrs["mj_first_discards"] = []
            for p in state.players.values():
                p.attrs["draw_count"] = 0
            # create dora_indicators zone if missing
            if "dora_indicators" not in state.zones:
                state.zones["dora_indicators"] = Zone(
                    "dora_indicators",
                    Visibility.PUBLIC,
                    Ordering.ORDERED,
                )
            # reveal one initial indicator from the back of the dead wall
            dead = state.zones.get("dead_wall")
            if dead and dead.items:
                ind = dead.pop(-1)
                state.zones["dora_indicators"].push(ind)
            return

        if isinstance(event, MeldFormed):
            # any meld clears ippatsu for everyone and kills tenhou/chiihou eligibility
            state.attrs["mj_any_call_yet"] = True
            for p in state.players.values():
                p.attrs["ippatsu"] = False
                p.attrs["ippatsu_skip_one"] = False
            # kan-type melds reveal one more dora
            if event.meld_type in (MINKAN, ANKAN, SHOUMINKAN):
                dead = state.zones.get("dead_wall")
                if dead and dead.items:
                    ind = dead.pop(-1)
                    state.zones["dora_indicators"].push(ind)
            return

        if isinstance(event, TileDrawn):
            state.attrs["mj_rinshan_pending"] = event.from_dead_wall
            p = state.players[event.seat]
            p.attrs["draw_count"] = p.attrs.get("draw_count", 0) + 1
            return

        if isinstance(event, TileDiscarded):
            # expire ippatsu for the discarder if they had it active (and weren't on the riichi discard)
            p = state.players[event.seat]
            if p.attrs.get("ippatsu"):
                if p.attrs.get("ippatsu_skip_one"):
                    p.attrs["ippatsu_skip_one"] = False
                else:
                    p.attrs["ippatsu"] = False
            # track first round discards (for 4-winds abort)
            if not state.attrs.get("mj_any_call_yet", False):
                fd = state.attrs.setdefault("mj_first_discards", [])
                if not any(s == event.seat for s, _ in fd):
                    tile = _find_tile_anywhere(state, event.tile_id)
                    if tile is not None:
                        fd.append((event.seat, tile.code))
            return

    # ---- internal -----------------------------------------------------------
    def _build_ctx(
        self,
        state: GameState,
        seat: PlayerId,
        winning_tile: Tile,
        is_tsumo: bool,
        declared: list[Meld],
    ) -> YakuContext:
        dealer = cast(int, state.attrs.get("mj_dealer_seat", 0))
        round_wind = cast(int, state.attrs.get("mj_round_wind", 1))
        p = state.players[seat]
        is_first_turn = (
            not state.attrs.get("mj_any_call_yet", False)
            and p.attrs.get("draw_count", 0) == 1
        )
        ctx = YakuContext(
            seat_wind=_seat_wind(seat, dealer, self.seats),
            round_wind=round_wind,
            is_tsumo=is_tsumo,
            is_riichi=bool(p.attrs.get("riichi")),
            is_double_riichi=bool(p.attrs.get("double_riichi")),
            is_ippatsu=bool(p.attrs.get("ippatsu")),
            is_rinshan=is_tsumo and bool(state.attrs.get("mj_rinshan_pending")),
            is_chankan=(not is_tsumo) and bool(state.attrs.get("mj_is_chankan_win")),
            is_tenhou=is_tsumo and is_first_turn and seat == dealer,
            is_chiihou=is_tsumo and is_first_turn and seat != dealer,
        )
        return ctx


# ---- module-level helpers --------------------------------------------------
def _count_dora_for_best(decomps, ctx: YakuContext, state: GameState) -> int:
    """Count dora across the winning hand using the currently-revealed dora indicators."""
    inds = list(state.zones.get("dora_indicators", Zone("x", Visibility.PUBLIC)).items)  # type: ignore[arg-type]
    return _count_dora_with_indicators(decomps, cast(list[Tile], inds))


def _count_dora_with_indicators(decomps, indicators: list[Tile]) -> int:
    if not indicators:
        return 0
    return max(_count_dora(d.groups, indicators) for d in decomps)


def _peek_ura_indicators(state: GameState) -> list[Tile]:
    """Ura-dora indicators: as many tiles from the dead wall as there are visible dora
    indicators. Visible only to riichi winners; we 'peek' without removing them.
    """
    dora = state.zones.get("dora_indicators")
    dead = state.zones.get("dead_wall")
    if dora is None or dead is None or not dora.items or not dead.items:
        return []
    n = min(len(dora.items), len(dead.items))
    # use a stable position — the deepest n tiles of dead_wall as the "ura" indicators
    return cast(list[Tile], list(dead.items[:n]))
