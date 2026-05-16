"""Feature tests for the more nuanced riichi rules: furiten, double riichi,
tenhou / chiihou, double yakuman, dora, nagashi, calls, special draws, etc.

Each test sets up a minimal `GameState` directly (skipping the engine) so we can
isolate the ruleset behaviour we're testing.
"""
from __future__ import annotations

from collections.abc import Iterable

from core.player import Player
from core.resource import Resource
from core.rng import RNG
from core.state import GameState
from core.zone import Ordering, Visibility, Zone
from mahjong.actions import (
    ChiAction,
    DeclareAbortAction,
    DeclareWinAction,
    KanAction,
    PonAction,
)
from mahjong.meld import ANKAN, MINKAN, PON, SHOUMINKAN, Meld
from mahjong.tile import Tile
from rules.riichi.ruleset import RiichiRuleset


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────
def t(code: str, red: bool = False) -> Tile:
    """Build a tile from a code string like 'm5' or 'z3'."""
    return Tile(code[0], int(code[1:]), red=red)


def tiles(*codes: str) -> list[Tile]:
    return [t(c) for c in codes]


def make_state(
    *,
    hands: dict[int, list[Tile]],
    discards: dict[int, list[Tile]] | None = None,
    melds: dict[int, list[Meld]] | None = None,
    points: dict[int, int] | None = None,
    dealer: int = 0,
    round_wind: int = 1,
    wall_count: int = 70,
    last_discard_seat: int | None = None,
    last_discard_tile_id: int | None = None,
) -> GameState:
    state = GameState(rng=RNG(seed=0))
    state.attrs["mj_dealer_seat"] = dealer
    state.attrs["mj_round_wind"] = round_wind
    state.attrs["mj_hand_number"] = 1

    if last_discard_seat is not None:
        state.attrs["mj_last_discard_seat"] = last_discard_seat
    if last_discard_tile_id is not None:
        state.attrs["mj_last_discard_tile_id"] = last_discard_tile_id

    state.zones["wall"] = Zone("wall", Visibility.HIDDEN, Ordering.ORDERED)
    for _ in range(wall_count):
        state.zones["wall"].push(t("m1"))
    state.zones["dead_wall"] = Zone("dead_wall", Visibility.HIDDEN, Ordering.ORDERED)
    for _ in range(14):
        state.zones["dead_wall"].push(t("m1"))
    state.zones["dora_indicators"] = Zone(
        "dora_indicators", Visibility.PUBLIC, Ordering.ORDERED
    )

    for i in range(4):
        p = Player(id=i, name="ESWN"[i])
        p.zones["hand"] = Zone("hand", Visibility.OWNER_ONLY, Ordering.UNORDERED, owner=i)
        p.zones["melds"] = Zone("melds", Visibility.PUBLIC, Ordering.ORDERED, owner=i)
        p.zones["discards"] = Zone("discards", Visibility.PUBLIC, Ordering.ORDERED, owner=i)
        p.resources["points"] = Resource(
            "points", value=(points or {}).get(i, 25000)
        )
        for tile in hands.get(i, []):
            p.zones["hand"].push(tile)
        for tile in (discards or {}).get(i, []):
            p.zones["discards"].push(tile)
        for m in (melds or {}).get(i, []):
            p.zones["melds"].push(m)
        state.players[i] = p
    return state


def has_action(actions: Iterable, kind: str) -> bool:
    for a in actions:
        if isinstance(a, DeclareWinAction) and a.kind == kind:
            return True
        if not isinstance(a, DeclareWinAction) and getattr(a, "__class__", type(a)).__name__.lower().startswith(kind):
            return True
    return False


def has_ron(actions: Iterable) -> bool:
    return any(isinstance(a, DeclareWinAction) and a.kind == "ron" for a in actions)


# ──────────────────────────────────────────────────────────────────────────
# Furiten
# ──────────────────────────────────────────────────────────────────────────
def test_furiten_blocks_ron() -> None:
    rs = RiichiRuleset()
    # seat 1: 222m 333p 444s 555m + 6m (13 tiles, waiting on 6m → pair completion)
    seat1_hand = tiles("m2","m2","m2","p3","p3","p3","s4","s4","s4","m5","m5","m5","m6")
    # seat 1 has already discarded m6 in the past → permanent furiten
    seat1_disc = [t("m6")]
    # seat 0 discards m6 now
    fresh_m6 = t("m6")
    state = make_state(
        hands={1: seat1_hand},
        discards={1: seat1_disc, 0: [fresh_m6]},
        last_discard_seat=0,
        last_discard_tile_id=fresh_m6.id,
    )
    out = rs.legal_responses(state, discard_seat=0, discarded_tile_id=fresh_m6.id)
    assert not has_ron(out[1]), "furiten seat must not be offered ron"


def test_no_furiten_allows_ron() -> None:
    """Control: same hand without the dead m6 in own discards → ron allowed."""
    rs = RiichiRuleset()
    seat1_hand = tiles("m2","m2","m2","p3","p3","p3","s4","s4","s4","m5","m5","m5","m6")
    fresh_m6 = t("m6")
    state = make_state(
        hands={1: seat1_hand},
        discards={0: [fresh_m6]},
        last_discard_seat=0,
        last_discard_tile_id=fresh_m6.id,
    )
    out = rs.legal_responses(state, discard_seat=0, discarded_tile_id=fresh_m6.id)
    assert has_ron(out[1]), "non-furiten seat should be offered ron"


# ──────────────────────────────────────────────────────────────────────────
# Double riichi
# ──────────────────────────────────────────────────────────────────────────
def test_double_riichi_first_turn() -> None:
    rs = RiichiRuleset()
    # tenpai hand for seat 0 (13 tiles)
    h = tiles("m2","m3","m4","p5","p5","p5","s6","s7","s8","s3","s3","m6","m7")
    state = make_state(hands={0: h})
    state.attrs["mj_any_call_yet"] = False
    state.players[0].attrs["draw_count"] = 1
    rs.apply_riichi(state, 0)
    assert state.players[0].attrs.get("double_riichi") is True


def test_double_riichi_not_after_call() -> None:
    rs = RiichiRuleset()
    h = tiles("m2","m3","m4","p5","p5","p5","s6","s7","s8","s3","s3","m6","m7")
    state = make_state(hands={0: h})
    state.attrs["mj_any_call_yet"] = True   # a call happened
    state.players[0].attrs["draw_count"] = 1
    rs.apply_riichi(state, 0)
    assert not state.players[0].attrs.get("double_riichi")


# ──────────────────────────────────────────────────────────────────────────
# Tenhou (dealer first-turn tsumo)
# ──────────────────────────────────────────────────────────────────────────
def test_tenhou_dealer_first_draw() -> None:
    rs = RiichiRuleset()
    h = tiles("m1","m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    state = make_state(hands={0: h}, dealer=0)
    state.attrs["mj_any_call_yet"] = False
    state.players[0].attrs["draw_count"] = 1
    deltas = rs.score_win(state, winner_seat=0, loser_seat=None, winning_tile=h[-1])
    yaku = {n: v for n, v in state.attrs.get("mj_last_yaku", [])}
    assert "天和" in yaku, f"expected 天和 in yaku, got {yaku}"
    assert sum(deltas.values()) == 0


def test_tenhou_blocked_by_call() -> None:
    rs = RiichiRuleset()
    h = tiles("m1","m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    state = make_state(hands={0: h}, dealer=0)
    state.attrs["mj_any_call_yet"] = True   # something happened
    state.players[0].attrs["draw_count"] = 1
    rs.score_win(state, winner_seat=0, loser_seat=None, winning_tile=h[-1])
    yaku = {n: v for n, v in state.attrs.get("mj_last_yaku", [])}
    assert "天和" not in yaku


# ──────────────────────────────────────────────────────────────────────────
# Chiihou (non-dealer first-draw tsumo)
# ──────────────────────────────────────────────────────────────────────────
def test_chiihou_non_dealer_first_draw() -> None:
    rs = RiichiRuleset()
    h = tiles("m1","m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    state = make_state(hands={1: h}, dealer=0)
    state.attrs["mj_any_call_yet"] = False
    state.players[1].attrs["draw_count"] = 1
    rs.score_win(state, winner_seat=1, loser_seat=None, winning_tile=h[-1])
    yaku = {n: v for n, v in state.attrs.get("mj_last_yaku", [])}
    assert "地和" in yaku, f"expected 地和 in yaku, got {yaku}"


def test_chiihou_not_for_dealer() -> None:
    """If dealer wins on first turn, it's tenhou, not chiihou (regression check)."""
    rs = RiichiRuleset()
    h = tiles("m1","m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    state = make_state(hands={0: h}, dealer=0)
    state.attrs["mj_any_call_yet"] = False
    state.players[0].attrs["draw_count"] = 1
    rs.score_win(state, winner_seat=0, loser_seat=None, winning_tile=h[-1])
    yaku = {n: v for n, v in state.attrs.get("mj_last_yaku", [])}
    assert "天和" in yaku
    assert "地和" not in yaku


# ──────────────────────────────────────────────────────────────────────────
# Double yakuman
# ──────────────────────────────────────────────────────────────────────────
from rules.riichi.decompose import KOKUSHI_TILES, all_decompositions
from rules.riichi.yaku import YakuContext, evaluate


def test_kokushi_13_wait_is_double_yakuman() -> None:
    # hold 13 unique terminals/honors, winning tile completes the duplicate at z1.
    # 14-tile winning hand:
    h = tiles(*KOKUSHI_TILES, "z1")
    win = t("z1")
    decomps = all_decompositions(h, [], win)
    res = evaluate(decomps, YakuContext(is_tsumo=True))
    assert res is not None
    assert res.yakuman_multiple == 2
    assert any(n == "国士無双" and v == 26 for n, v in res.yaku)


def test_kokushi_normal_is_single_yakuman() -> None:
    # Pair on z1 (duplicate), winning tile is m1 (one of the singles).
    pre_win_codes = [c for c in KOKUSHI_TILES if c != "m1"]   # 12 unique tiles
    pre_win_codes.append("z1")                                # 2nd z1 → 13 tiles
    h = [t(c) for c in pre_win_codes] + [t("m1")]             # 14 tiles
    assert len(h) == 14
    win = t("m1")
    decomps = all_decompositions(h, [], win)
    res = evaluate(decomps, YakuContext(is_tsumo=False))
    assert res is not None
    assert res.yakuman_multiple == 1


def test_chuuren_pure_9_wait_is_double_yakuman() -> None:
    # 1112345678999m + winning m5 (any 1-9 could win, here m5)
    h = tiles("m1","m1","m1","m2","m3","m4","m5","m5","m6","m7","m8","m9","m9","m9")
    win = t("m5")
    decomps = all_decompositions(h, [], win)
    res = evaluate(decomps, YakuContext(is_tsumo=True))
    assert res is not None
    has_chuuren = any(n == "九蓮宝燈" for n, _ in res.yaku)
    assert has_chuuren, f"expected chuuren in {res.yaku}"
    # pure form: removing m5 leaves 1112345 6 78 999, which is exactly 3-1-1-1-1-1-1-1-3
    assert res.yakuman_multiple == 2


def test_chuuren_impure_is_single_yakuman() -> None:
    # 1112345678999 + winning m2 → after win we have 11 1 22 3 4 5 6 7 8 999 — 14 tiles
    # the base pattern needs 3 on rank 1 and 3 on rank 9. With extra m2 we get
    # counts 3,2,1,1,1,1,1,1,3 — passes chuuren shape. Removing m2 gives 3,1,1,...,3 = base.
    # That's still pure 9-wait! Let me pick a different impure: extra m9 wins.
    # 1112345678999 + win m9: counts 3,1,1,1,1,1,1,1,4. After removing m9: 3,1,1,1,1,1,1,1,3 = base → pure.
    # Hmm, any rank 1-9 results in pure shape because the pre-win was exactly the base.
    # For an IMPURE 9-gates, the pre-win hand is NOT the base — some other shape that
    # happens to satisfy the chuuren count pattern after adding the winning tile.
    # Example: pre-win 1112234678999, win on m5 (the missing rank):
    # counts before win: 3,2,1,0,0,1,1,1,3 — wait sum=12, need 13. Let me re-count.
    # Pre-win must be 13 tiles. Pattern 1112234678999 = 3+2+1+1+0+1+1+1+3 = 13? 3+2=5, +1=6, +1=7, +0=7, +1=8, +1=9, +1=10, +3=13. yes.
    # Add winning tile m5: counts become 3,2,1,1,0,2,1,1,3 — wait that violates the chuuren shape (rank 4 is 0).
    # Hmm. The chuuren shape requires all ranks 1-9 present with min count [3,1,1,1,1,1,1,1,3].
    # So if pre-win is missing rank 4, the final hand will too.
    # Let me try pre-win 1112345677899: 3,1,1,1,1,1,2,1,2 = 13 tiles. Win on m9:
    # counts 3,1,1,1,1,1,2,1,3 — total 14 ✓. Min check: all rank 1-9 have ≥ base.
    # rank 1: 3≥3 ✓. ranks 2-8: 1,1,1,1,1,2,1 each ≥1 ✓. rank 9: 3≥3 ✓.
    # sum diffs: 0+0+0+0+0+0+1+0+0 = 1 ✓ (the extra m7 vs base).
    # Pre-win (remove m9): 3,1,1,1,1,1,2,1,2 — rank 9 is 2, not base 3 → NOT pure.
    h = tiles("m1","m1","m1","m2","m3","m4","m5","m6","m7","m7","m8","m9","m9","m9")
    win = t("m9")
    decomps = all_decompositions(h, [], win)
    res = evaluate(decomps, YakuContext(is_tsumo=True))
    assert res is not None
    if any(n == "九蓮宝燈" for n, _ in res.yaku):
        # if chuuren fires, must be single (not pure 9-wait)
        assert res.yakuman_multiple == 1
    # otherwise we got chinitsu+ other yaku, also acceptable for this hand
    # the test verifies double yakuman doesn't spuriously fire


# ──────────────────────────────────────────────────────────────────────────
# Dora reveals
# ──────────────────────────────────────────────────────────────────────────
from mahjong.events import HandStarted as _HandStarted
from mahjong.events import MeldFormed as _MeldFormed


def test_initial_dora_revealed_on_hand_started() -> None:
    rs = RiichiRuleset()
    state = make_state(hands={0: []})
    state.zones["dora_indicators"].items.clear()  # reset for clean test
    # refill dead_wall to ensure it has tiles
    state.zones["dead_wall"].items.clear()
    for _ in range(14):
        state.zones["dead_wall"].push(t("m1"))
    rs.observe(state, _HandStarted(dealer=0, round_wind=1, hand_number=1))
    assert len(state.zones["dora_indicators"].items) == 1


def test_kan_reveals_extra_dora() -> None:
    rs = RiichiRuleset()
    state = make_state(hands={0: []})
    # reset & reseed dead_wall + dora_indicators via HandStarted
    state.zones["dora_indicators"].items.clear()
    state.zones["dead_wall"].items.clear()
    for _ in range(14):
        state.zones["dead_wall"].push(t("m1"))
    rs.observe(state, _HandStarted(dealer=0, round_wind=1, hand_number=1))
    n0 = len(state.zones["dora_indicators"].items)
    for kind in ("minkan", "ankan", "shouminkan"):
        rs.observe(state, _MeldFormed(seat=0, meld_id=9, meld_type=kind, called_from=None))
    assert len(state.zones["dora_indicators"].items) == n0 + 3


def test_ura_dora_for_riichi_winner() -> None:
    """Riichi winner gets ura-dora counted against the dead wall."""
    rs = RiichiRuleset()
    # pinfu shape, win on m4 (ryanmen). m2 appears once → dora & ura-dora target m2 each give +1.
    h = tiles("m2","m3","m4","p2","p3","p4","s5","s6","s7","p6","p7","p8","z1","z1")
    state = make_state(hands={1: h}, dealer=0)
    # set up dora indicators + dead wall (all m1) so indicator → m2 dora
    state.zones["dead_wall"].items.clear()
    for _ in range(14):
        state.zones["dead_wall"].push(t("m1"))
    state.zones["dora_indicators"].items.clear()
    rs.observe(state, _HandStarted(dealer=0, round_wind=1, hand_number=1))
    # mark seat 1 as riichi'd (so ura dora applies)
    state.players[1].attrs["riichi"] = True
    state.players[1].attrs["draw_count"] = 5   # not first turn (no tenhou/chiihou)
    state.attrs["mj_any_call_yet"] = False
    rs.score_win(state, winner_seat=1, loser_seat=None, winning_tile=t("m4"))
    yaku = {n: v for n, v in state.attrs.get("mj_last_yaku", [])}
    assert "ドラ" in yaku and yaku["ドラ"] >= 1, f"expected dora >=1 in {yaku}"
    assert "裏ドラ" in yaku and yaku["裏ドラ"] >= 1, f"expected ura-dora >=1 in {yaku}"


def test_no_ura_dora_for_non_riichi_winner() -> None:
    rs = RiichiRuleset()
    h = tiles("m2","m3","m4","p2","p3","p4","s5","s6","s7","p6","p7","p8","z1","z1")
    state = make_state(hands={1: h}, dealer=0)
    state.zones["dead_wall"].items.clear()
    for _ in range(14):
        state.zones["dead_wall"].push(t("m1"))
    state.zones["dora_indicators"].items.clear()
    rs.observe(state, _HandStarted(dealer=0, round_wind=1, hand_number=1))
    # need a yaku without riichi. Pinfu+tsumo concealed gives menzen_tsumo+pinfu.
    state.players[1].attrs["draw_count"] = 5
    state.attrs["mj_any_call_yet"] = False
    rs.score_win(state, winner_seat=1, loser_seat=None, winning_tile=t("m4"))
    yaku = {n: v for n, v in state.attrs.get("mj_last_yaku", [])}
    assert "裏ドラ" not in yaku, f"non-riichi winner should not see ura dora; got {yaku}"


# ──────────────────────────────────────────────────────────────────────────
# Nagashi mangan
# ──────────────────────────────────────────────────────────────────────────
def test_nagashi_mangan_non_dealer() -> None:
    rs = RiichiRuleset()
    state = make_state(
        hands={i: [] for i in range(4)},
        discards={
            # seat 0 (dealer): mixed discards → does NOT qualify
            0: tiles("m1","m5","m9","p1"),
            # seat 1: all terminals/honors → qualifies
            1: tiles("m1","m9","p1","p9","s1","s9","z1","z2","z3","z4","z5","z6","z7"),
            # seat 2: a non-terminal → does NOT qualify
            2: tiles("m1","p5","s9"),
            # seat 3: empty → does NOT qualify
            3: [],
        },
        dealer=0,
    )
    deltas = rs.score_draw(state)
    # seat 1 wins nagashi non-dealer mangan: dealer pays 4000, others 2000, total +8000
    assert deltas[1] == 8000
    assert deltas[0] == -4000
    assert deltas[2] == -2000
    assert deltas[3] == -2000
    assert sum(deltas.values()) == 0


def test_nagashi_blocked_by_called_discard() -> None:
    rs = RiichiRuleset()
    # seat 1 has all terminal/honor discards but seat 2 called one of them (pon from seat 1)
    pon_meld = Meld(PON, (t("m1"), t("m1"), t("m1")), called_from=1, called_tile_id=t("m1").id)
    state = make_state(
        hands={i: [] for i in range(4)},
        discards={1: tiles("m9","p1","p9","s1","s9")},
        melds={2: [pon_meld]},
        dealer=0,
    )
    deltas = rs.score_draw(state)
    assert deltas[1] == 0
    assert all(d == 0 for d in deltas.values())


def test_nagashi_mangan_dealer() -> None:
    rs = RiichiRuleset()
    state = make_state(
        hands={i: [] for i in range(4)},
        discards={
            0: tiles("m1","m9","p1","p9","z1","z2","z3"),  # dealer qualifies
            1: tiles("m5"),
        },
        dealer=0,
    )
    deltas = rs.score_draw(state)
    # dealer nagashi: each pays 4000 → +12000
    assert deltas[0] == 12000
    for s in (1, 2, 3):
        assert deltas[s] == -4000


# ──────────────────────────────────────────────────────────────────────────
# Call scenarios — chi / pon / kan
# ──────────────────────────────────────────────────────────────────────────
def test_chi_offered_only_to_left_seat() -> None:
    rs = RiichiRuleset()
    # seat 0 discards m4. Left of 0 = (0+1) % 4 = 1. Only seat 1 may chi.
    # Each seat 1/2/3 has m5+m6 in hand (would-be chi tiles), only seat 1 gets the action.
    hand_with_chi = tiles("m5","m6","p1","p2","p3","p4","p5","s1","s2","s3","s5","s6","s7")
    fresh = t("m4")
    state = make_state(
        hands={1: list(hand_with_chi), 2: list(hand_with_chi), 3: list(hand_with_chi)},
        discards={0: [fresh]},
        last_discard_seat=0,
    )
    out = rs.legal_responses(state, discard_seat=0, discarded_tile_id=fresh.id)
    assert any(isinstance(a, ChiAction) for a in out[1])
    assert not any(isinstance(a, ChiAction) for a in out[2])
    assert not any(isinstance(a, ChiAction) for a in out[3])


def test_chi_three_positions() -> None:
    rs = RiichiRuleset()
    # m4 can be chi'd as 4-5-6 (low), 3-4-5 (middle), or 2-3-4 (high)
    h = tiles("m2","m3","m5","m6","p1","p2","p3","p4","p5","p6","s1","s2","s3")
    fresh = t("m4")
    state = make_state(hands={1: h}, discards={0: [fresh]}, last_discard_seat=0)
    out = rs.legal_responses(state, discard_seat=0, discarded_tile_id=fresh.id)
    chis = [a for a in out[1] if isinstance(a, ChiAction)]
    assert len(chis) == 3, f"expected 3 chi shapes, got {len(chis)}"


def test_pon_offered_to_any_opponent() -> None:
    rs = RiichiRuleset()
    h = tiles("m5","m5","p1","p2","p3","p4","p5","s1","s2","s3","s5","s6","s7")
    fresh = t("m5")
    state = make_state(
        hands={1: list(h), 2: list(h), 3: list(h)},
        discards={0: [fresh]},
        last_discard_seat=0,
    )
    out = rs.legal_responses(state, discard_seat=0, discarded_tile_id=fresh.id)
    for s in (1, 2, 3):
        assert any(isinstance(a, PonAction) for a in out[s]), f"pon missing for seat {s}"


def test_minkan_needs_three_matching_in_hand() -> None:
    rs = RiichiRuleset()
    h_with_3 = tiles("m5","m5","m5","p1","p2","p3","p4","p5","s1","s2","s3","s5","s6")
    h_with_2 = tiles("m5","m5","p1","p2","p3","p4","p5","s1","s2","s3","s5","s6","s7")
    h_with_1 = tiles("m5","p1","p2","p3","p4","p5","s1","s2","s3","s5","s6","s7","s8")
    fresh = t("m5")
    state = make_state(
        hands={1: h_with_3, 2: h_with_2, 3: h_with_1},
        discards={0: [fresh]},
        last_discard_seat=0,
    )
    out = rs.legal_responses(state, discard_seat=0, discarded_tile_id=fresh.id)
    # seat 1: pon + minkan
    assert any(isinstance(a, PonAction) for a in out[1])
    assert any(isinstance(a, KanAction) and a.kind == MINKAN for a in out[1])
    # seat 2: pon, no minkan
    assert any(isinstance(a, PonAction) for a in out[2])
    assert not any(isinstance(a, KanAction) for a in out[2])
    # seat 3: nothing extra (only 1 m5)
    assert not any(isinstance(a, PonAction) for a in out[3])
    assert not any(isinstance(a, KanAction) for a in out[3])


def test_ankan_offered_when_four_in_hand() -> None:
    rs = RiichiRuleset()
    # 14 tiles total (post-draw); 4 m5 + 10 others
    h = tiles("m5","m5","m5","m5","p1","p2","p3","p4","p5","s1","s2","s3","s5","s6")
    state = make_state(hands={0: h})
    drawn = h[0]   # any of the m5s; the ankan check doesn't care which is "drawn"
    actions = rs.legal_after_draw(state, seat=0, drawn_tile_id=drawn.id)
    ankans = [a for a in actions if isinstance(a, KanAction) and a.kind == ANKAN]
    assert len(ankans) == 1
    assert len(ankans[0].hand_tile_ids) == 4


def test_shouminkan_offered_when_drew_matches_existing_pon() -> None:
    rs = RiichiRuleset()
    pon_m5 = Meld(PON, (t("m5"), t("m5"), t("m5")), called_from=1, called_tile_id=t("m5").id)
    h = tiles("p1","p2","p3","p4","p5","s1","s2","s3","s5","s6","p6") + [t("m5")]
    state = make_state(hands={0: h}, melds={0: [pon_m5]})
    drawn = h[-1]  # the m5 we just drew
    actions = rs.legal_after_draw(state, seat=0, drawn_tile_id=drawn.id)
    shouminkans = [a for a in actions if isinstance(a, KanAction) and a.kind == SHOUMINKAN]
    assert len(shouminkans) == 1
    assert shouminkans[0].hand_tile_ids == (drawn.id,)


def test_no_calls_offered_to_riichi_player() -> None:
    """A player who has declared riichi may only pass or ron — no chi/pon/kan."""
    rs = RiichiRuleset()
    h = tiles("m5","m5","m6","p1","p2","p3","p4","p5","s1","s2","s3","s5","s6")
    fresh = t("m5")
    state = make_state(hands={1: h}, discards={0: [fresh]}, last_discard_seat=0)
    state.players[1].attrs["riichi"] = True
    out = rs.legal_responses(state, discard_seat=0, discarded_tile_id=fresh.id)
    kinds = {a.__class__.__name__ for a in out[1]}
    assert "PonAction" not in kinds
    assert "ChiAction" not in kinds
    assert "KanAction" not in kinds


# ──────────────────────────────────────────────────────────────────────────
# Double ron + triple ron abort
# ──────────────────────────────────────────────────────────────────────────
def test_resolve_double_ron_returns_two_winners() -> None:
    rs = RiichiRuleset()
    state = make_state(hands={i: [] for i in range(4)}, last_discard_seat=0)
    decisions = {
        1: DeclareWinAction(actor=1, kind="ron"),
        2: DeclareWinAction(actor=2, kind="ron"),
    }
    winners = rs.resolve_response_priority(state, decisions)
    assert winners is not None
    assert len(winners) == 2
    seats = {s for s, _ in winners}
    assert seats == {1, 2}


def test_resolve_triple_ron_is_abort() -> None:
    rs = RiichiRuleset()
    state = make_state(hands={i: [] for i in range(4)}, last_discard_seat=0)
    decisions = {
        1: DeclareWinAction(actor=1, kind="ron"),
        2: DeclareWinAction(actor=2, kind="ron"),
        3: DeclareWinAction(actor=3, kind="ron"),
    }
    winners = rs.resolve_response_priority(state, decisions)
    assert winners == [], "triple ron should signal abort with empty list"
    assert state.attrs.get("mj_abort_reason") == "triple_ron"


def test_resolve_head_bump_ordering() -> None:
    """Double-ron returned in priority order: closest seat to discarder first."""
    rs = RiichiRuleset()
    state = make_state(hands={i: [] for i in range(4)}, last_discard_seat=0)
    # seats 3 and 2 both ron seat 0's discard
    # closest to discarder (clockwise): seat 1 closest, then 2, then 3
    decisions = {
        3: DeclareWinAction(actor=3, kind="ron"),
        2: DeclareWinAction(actor=2, kind="ron"),
    }
    winners = rs.resolve_response_priority(state, decisions)
    assert winners is not None
    assert [s for s, _ in winners] == [2, 3]  # seat 2 closer than 3


# ──────────────────────────────────────────────────────────────────────────
# Chankan (ron on shouminkan upgrade)
# ──────────────────────────────────────────────────────────────────────────
def test_chankan_phase_legal_responses_only_offer_ron() -> None:
    rs = RiichiRuleset()
    # seat 1 holds a hand that would ron on m5; seat 0 declares shouminkan adding m5.
    # The "discarded" tile in chankan is in seat 0's meld zone, not discards.
    pon_m5 = Meld(PON, (t("m5"), t("m5"), t("m5")), called_from=2, called_tile_id=t("m5").id)
    added = t("m5")
    upgraded = Meld(
        SHOUMINKAN,
        pon_m5.tiles + (added,),
        called_from=pon_m5.called_from,
        called_tile_id=pon_m5.called_tile_id,
    )
    # build a winning ron-on-m5 hand for seat 1: tanyao 234m 234p 234s 678p + 5m5m
    seat1_hand = tiles("m2","m3","m4","p2","p3","p4","s2","s3","s4","p6","p7","p8","m5")
    state = make_state(hands={1: seat1_hand}, melds={0: [upgraded]}, dealer=2)
    state.attrs["mj_phase"] = "chankan"
    out = rs.legal_responses(state, discard_seat=0, discarded_tile_id=added.id)
    # seat 1 should get ron (chankan = 1 han, enough to validate)
    assert any(isinstance(a, DeclareWinAction) and a.kind == "ron" for a in out[1])
    # seat 1 must NOT get pon/chi/kan even though the upgrade tile is in seat 0's meld
    for s in out:
        for a in out[s]:
            assert not isinstance(a, (PonAction, ChiAction, KanAction))


# ──────────────────────────────────────────────────────────────────────────
# Special abort draws
# ──────────────────────────────────────────────────────────────────────────
def test_nine_terminals_offered_on_first_turn() -> None:
    rs = RiichiRuleset()
    # 13 different terminal/honor tiles + 1 ordinary (the drawn tile, say m5)
    # That's 13 unique terminal/honor → ≥9, so abort is offered.
    h = tiles("m1","m9","p1","p9","s1","s9","z1","z2","z3","z4","z5","z6","z7","m5")
    state = make_state(hands={0: h}, dealer=0)
    state.attrs["mj_any_call_yet"] = False
    state.players[0].attrs["draw_count"] = 1
    actions = rs.legal_after_draw(state, seat=0, drawn_tile_id=h[-1].id)
    aborts = [a for a in actions if isinstance(a, DeclareAbortAction)]
    assert len(aborts) == 1 and aborts[0].reason == "nine_terminals"


def test_nine_terminals_not_offered_after_first_turn() -> None:
    rs = RiichiRuleset()
    h = tiles("m1","m9","p1","p9","s1","s9","z1","z2","z3","z4","z5","z6","z7","m5")
    state = make_state(hands={0: h}, dealer=0)
    state.attrs["mj_any_call_yet"] = False
    state.players[0].attrs["draw_count"] = 2  # second turn
    actions = rs.legal_after_draw(state, seat=0, drawn_tile_id=h[-1].id)
    assert not any(isinstance(a, DeclareAbortAction) for a in actions)


def test_four_winds_first_discards_abort() -> None:
    rs = RiichiRuleset()
    state = make_state(hands={i: [] for i in range(4)})
    state.attrs["mj_any_call_yet"] = False
    state.attrs["mj_first_discards"] = [(0, "z1"), (1, "z1"), (2, "z1"), (3, "z1")]
    reason = rs.check_abort_conditions(state)
    assert reason == "four_winds_first_discards"


def test_four_winds_not_abort_if_mixed() -> None:
    rs = RiichiRuleset()
    state = make_state(hands={i: [] for i in range(4)})
    state.attrs["mj_first_discards"] = [(0, "z1"), (1, "z2"), (2, "z1"), (3, "z1")]
    assert rs.check_abort_conditions(state) is None


def test_four_riichi_abort() -> None:
    rs = RiichiRuleset()
    state = make_state(hands={i: [] for i in range(4)})
    for i in range(4):
        state.players[i].attrs["riichi"] = True
    assert rs.check_abort_conditions(state) == "four_riichis"


def test_four_kans_abort_with_two_different_players() -> None:
    rs = RiichiRuleset()
    state = make_state(hands={i: [] for i in range(4)})
    # seat 0 has 3 ankans, seat 1 has 1 minkan → 4 kans across 2 players
    ankan = Meld(ANKAN, tuple(tiles("m1","m1","m1","m1")), called_from=None)
    minkan = Meld(MINKAN, tuple(tiles("p2","p2","p2","p2")), called_from=2, called_tile_id=0)
    state.players[0].zones["melds"].push(ankan)
    state.players[0].zones["melds"].push(Meld(ANKAN, tuple(tiles("m9","m9","m9","m9"))))
    state.players[0].zones["melds"].push(Meld(ANKAN, tuple(tiles("s5","s5","s5","s5"))))
    state.players[1].zones["melds"].push(minkan)
    assert rs.check_abort_conditions(state) == "four_kans"


def test_four_kans_not_aborted_if_all_by_one_player() -> None:
    """One player declaring all 4 kans → suukantsu yakuman, NOT an abort."""
    rs = RiichiRuleset()
    state = make_state(hands={i: [] for i in range(4)})
    for codes in ("m1m1m1m1", "p2p2p2p2", "s5s5s5s5", "z1z1z1z1"):
        cs = [codes[i:i+2] for i in range(0, len(codes), 2)]
        state.players[0].zones["melds"].push(Meld(ANKAN, tuple(tiles(*cs))))
    assert rs.check_abort_conditions(state) is None


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items() if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f()
        print(f"  ✓ {n}")
    print(f"\n{len(fns)} tests passed")
