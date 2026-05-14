"""Unit tests for SimpleRuleset's win detection — the algorithm we most want to pin down."""
from __future__ import annotations

from mahjong.tile import Tile, SUIT_M, SUIT_P, SUIT_S
from rules.simple import SimpleRuleset, _can_form_n_melds


def _hand(*codes: str) -> list[Tile]:
    out = []
    for c in codes:
        out.append(Tile(c[0], int(c[1:])))
    return out


def test_chitoitsu_not_a_win_in_simple() -> None:
    # 7 non-adjacent pairs: cannot be cut into 4 sequences/triplets + 1 pair
    rs = SimpleRuleset()
    h = _hand("m1","m1","m5","m5","m9","m9","p1","p1","p9","p9","s1","s1","s9","s9")
    assert not rs.is_winning_hand(h, [], h[-1], {})


def test_seven_consecutive_pairs_is_actually_a_win() -> None:
    # 7 consecutive-rank pairs (m1..m7) happens to decompose as m2m3m4 + m2m3m4 + m5m6m7 + m5m6m7 + m1m1
    rs = SimpleRuleset()
    h = _hand("m1","m1","m2","m2","m3","m3","m4","m4","m5","m5","m6","m6","m7","m7")
    assert rs.is_winning_hand(h, [], h[-1], {})


def test_all_triplets_win() -> None:
    rs = SimpleRuleset()
    # 4 triplets + 1 pair, 14 tiles
    h = _hand("m1","m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    assert rs.is_winning_hand(h, [], h[0], {})


def test_runs_and_triplets_mixed_win() -> None:
    rs = SimpleRuleset()
    # 234m + 567p + 234s + 999m + 11p pair
    h = _hand("m2","m3","m4","p5","p6","p7","s2","s3","s4","m9","m9","m9","p1","p1")
    assert rs.is_winning_hand(h, [], h[-1], {})


def test_missing_pair_fails() -> None:
    rs = SimpleRuleset()
    # 5 perfect triplets, no pair — over 14 tiles, sanity check that the algo respects shape
    h = _hand("m1","m1","m1","m2","m2","m2","m3","m3","m3","m4","m4","m4","m5","m5","m5")
    assert not rs.is_winning_hand(h, [], h[0], {})


def test_one_off_tenpai_not_win() -> None:
    rs = SimpleRuleset()
    # 13 tiles that are 1-shanten away — passing the discarded tile completes
    base = _hand("m1","m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5")
    p5 = Tile(SUIT_P, 5)
    assert rs.is_winning_hand(base + [p5], [], p5, {})
    # whereas a wrong completion doesn't win
    s7 = Tile(SUIT_S, 7)
    assert not rs.is_winning_hand(base + [s7], [], s7, {})


def test_with_meld_uses_remaining_tiles_only() -> None:
    rs = SimpleRuleset()
    # 3 melds in hand + 1 already-declared meld (a pon-equivalent) + pair → 11 tiles in hand
    from mahjong.meld import Meld, PON
    meld_tiles = (Tile(SUIT_M, 1), Tile(SUIT_M, 1), Tile(SUIT_M, 1))
    pon = Meld(PON, meld_tiles, called_from=0, called_tile_id=meld_tiles[2].id)
    h = _hand("p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    assert rs.is_winning_hand(h, [pon], h[-1], {})


def test_can_form_two_melds_basic() -> None:
    counts = {"m1": 3, "m2": 1, "m3": 1, "m4": 1}
    assert _can_form_n_melds(counts.copy(), 2)


def test_cannot_form_when_tiles_dont_match() -> None:
    counts = {"m1": 1, "p2": 1, "s3": 1}
    assert not _can_form_n_melds(counts.copy(), 1)


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [f for name, f in vars(mod).items() if name.startswith("test_") and callable(f)]
    for f in fns:
        f()
        print(f"  ✓ {f.__name__}")
    print(f"\n{len(fns)} tests passed")
