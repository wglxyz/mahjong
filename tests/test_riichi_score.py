"""Tests for fu calculation and payout distribution."""
from __future__ import annotations

from mahjong.tile import Tile
from rules.riichi.decompose import all_decompositions
from rules.riichi.score import base_points, calculate_payouts, score
from rules.riichi.yaku import YakuContext, evaluate


def _tiles(*codes: str) -> list[Tile]:
    return [Tile(c[0], int(c[1:])) for c in codes]


def test_base_points_table() -> None:
    # mangan
    assert base_points(5, 30, 0) == 2000
    # haneman
    assert base_points(6, 30, 0) == 3000
    assert base_points(7, 60, 0) == 3000
    # baiman
    assert base_points(8, 30, 0) == 4000
    # sanbaiman
    assert base_points(11, 30, 0) == 6000
    # kazoe yakuman
    assert base_points(13, 30, 0) == 8000
    # yakuman
    assert base_points(0, 0, 1) == 8000
    assert base_points(0, 0, 2) == 16000  # double yakuman stacked
    # below mangan: cap at 2000
    assert base_points(1, 30, 0) == 240   # 30 * 2^3
    assert base_points(4, 80, 0) == 2000  # would be 80 * 64 = 5120 → capped


def test_payouts_ron_non_dealer() -> None:
    # non-dealer winner, mangan (base 2000), ron from another non-dealer
    p = calculate_payouts(base=2000, is_tsumo=False, winner_seat=1, loser_seat=2, dealer_seat=0)
    assert p[1] == 8000
    assert p[2] == -8000
    assert p[0] == 0 and p[3] == 0


def test_payouts_ron_dealer() -> None:
    # dealer winner, mangan, ron
    p = calculate_payouts(base=2000, is_tsumo=False, winner_seat=0, loser_seat=2, dealer_seat=0)
    assert p[0] == 12000
    assert p[2] == -12000


def test_payouts_tsumo_non_dealer() -> None:
    # non-dealer tsumo, mangan: dealer pays 4000, each non-dealer pays 2000
    p = calculate_payouts(base=2000, is_tsumo=True, winner_seat=1, loser_seat=None, dealer_seat=0)
    assert p[1] == 8000
    assert p[0] == -4000
    assert p[2] == -2000
    assert p[3] == -2000


def test_payouts_tsumo_dealer() -> None:
    # dealer tsumo mangan: each pays 4000
    p = calculate_payouts(base=2000, is_tsumo=True, winner_seat=0, loser_seat=None, dealer_seat=0)
    assert p[0] == 12000
    for s in (1, 2, 3):
        assert p[s] == -4000


def test_payouts_round_up_to_100() -> None:
    # base 1300 → tsumo non-dealer: dealer pays ceil100(2600)=2600, others pay ceil100(1300)=1300
    # but if base were 1320, ceil100(2640) → 2700
    p = calculate_payouts(base=1320, is_tsumo=True, winner_seat=1, loser_seat=None, dealer_seat=0)
    assert p[0] == -2700
    assert p[2] == -1400


def test_score_tanyao_pinfu_ron_30fu_1han() -> None:
    # 4 runs + valueless pair (s5s5), ron on m4 (high side of m234 — ryanmen, pinfu)
    h = _tiles("m2","m3","m4","p3","p4","p5","s2","s3","s4","p6","p7","p8","s5","s5")
    win = Tile("m", 4)
    decomps = all_decompositions(h, [], win)
    ctx = YakuContext(is_tsumo=False)
    r = evaluate(decomps, ctx)
    assert r is not None
    deltas, fu, base = score(r, ctx, winner_seat=1, loser_seat=2, dealer_seat=0)
    # tanyao (1) + pinfu (1) = 2 han, 30 fu pinfu ron
    assert fu == 30
    # base = 30 * 2^4 = 480; non-dealer ron, loser pays 4 * 480 = 1920 → ceil100 = 2000
    assert deltas[1] == 2000
    assert deltas[2] == -2000


def test_score_dealer_riichi_tsumo() -> None:
    # all triplets (toitoi+sanankou), all simples; dealer tsumo with riichi
    h = _tiles("m2","m2","m2","p3","p3","p3","s5","s5","s5","m7","m7","m7","p8","p8")
    win = Tile("p", 8)
    decomps = all_decompositions(h, [], win)
    ctx = YakuContext(is_tsumo=True, is_riichi=True, seat_wind=1, round_wind=1)
    r = evaluate(decomps, ctx)
    assert r is not None
    # 4 concealed triplets → suuankou yakuman. yakuman > regular yaku.
    assert r.yakuman_multiple >= 1
    deltas, fu, base = score(r, ctx, winner_seat=0, loser_seat=None, dealer_seat=0)
    # dealer tsumo yakuman: each pays 16000
    assert deltas[0] == 48000
    for s in (1, 2, 3):
        assert deltas[s] == -16000


def test_payouts_zero_sum() -> None:
    p = calculate_payouts(base=2000, is_tsumo=True, winner_seat=2, loser_seat=None, dealer_seat=0)
    assert sum(p.values()) == 0
    p = calculate_payouts(base=2000, is_tsumo=False, winner_seat=2, loser_seat=3, dealer_seat=0)
    assert sum(p.values()) == 0


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items() if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f()
        print(f"  ✓ {n}")
    print(f"\n{len(fns)} tests passed")
