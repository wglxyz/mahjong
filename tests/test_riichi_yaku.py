"""Tests for riichi yaku detection."""
from __future__ import annotations

from mahjong.tile import Tile
from rules.riichi.decompose import KOKUSHI_TILES, all_decompositions
from rules.riichi.yaku import YakuContext, evaluate


def _tiles(*codes: str) -> list[Tile]:
    return [Tile(c[0], int(c[1:])) for c in codes]


def _eval(h, declared=None, win=None, **ctx_kwargs):
    declared = declared or []
    if win is None:
        win = h[-1]
    decomps = all_decompositions(h, declared, win)
    return evaluate(decomps, YakuContext(**ctx_kwargs))


def test_yakuless_returns_none() -> None:
    # 4 different-suit runs + tanki pair wait; no sanshoku, no iipeiko, no ittsu,
    # no yakuhai, no tanyao (p1 terminal in pair). Ron on p1 → tanki wait, NOT pinfu.
    h = _tiles("m2","m3","m4","p5","p6","p7","s2","s3","s4","s6","s7","s8","p1","p1")
    win = Tile("p", 1)
    decomps = all_decompositions(h, [], win)
    result = evaluate(decomps, YakuContext(is_tsumo=False))
    assert result is None, f"expected yakuless, got {[n for n,_ in result.yaku]}"


def test_tanyao() -> None:
    h = _tiles("m2","m3","m4","p5","p5","p5","s6","s7","s8","s3","s3","m6","m7","m8")
    result = _eval(h, win=Tile("s", 8), is_tsumo=True)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "断幺九" in names


def test_riichi_tsumo() -> None:
    h = _tiles("m2","m3","m4","p5","p5","p5","s6","s7","s8","s3","s3","m6","m7","m8")
    result = _eval(h, win=Tile("s", 8), is_tsumo=True, is_riichi=True)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "立直" in names
    assert "門前清自摸和" in names


def test_yakuhai_dragon() -> None:
    h = _tiles("m1","m2","m3","p4","p5","p6","s7","s8","s9","z5","z5","z5","s1","s1")
    result = _eval(h, win=Tile("s", 1), is_tsumo=True)
    assert result is not None
    names = {n: v for n, v in result.yaku}
    assert "役牌" in names and names["役牌"] >= 1


def test_pinfu_proper_ryanmen() -> None:
    # 4 runs + valueless pair (p1p1), win on outer tile (s8 with s67_ wait)
    h = _tiles("m2","m3","m4","p4","p5","p6","s2","s3","s4","s6","s7","s8","p1","p1")
    win = Tile("s", 8)
    result = _eval(h, win=win, is_tsumo=False)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "平和" in names


def test_iipeiko() -> None:
    h = _tiles("m2","m3","m4","m2","m3","m4","p5","p6","p7","s1","s2","s3","z3","z3")
    result = _eval(h, win=Tile("s", 3), is_tsumo=False)
    assert result is not None
    names = {n for n, _ in result.yaku}
    # No simpler yaku here (pair = z3 west not seat/round in default), so we need iipeiko
    # to be present.
    assert "一盃口" in names


def test_chiitoitsu() -> None:
    h = _tiles("m1","m1","m5","m5","m9","m9","p1","p1","p9","p9","s1","s1","s9","s9")
    result = _eval(h, win=Tile("s", 9), is_tsumo=True)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "七対子" in names


def test_toitoi() -> None:
    # ron on m1 — breaks suuankou (the m1 triplet was ron'd), so we get toitoi+sanankou
    h_pre = _tiles("m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    result = _eval(h_pre + _tiles("m1"), win=Tile("m", 1), is_tsumo=False)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "対々和" in names


def test_honitsu() -> None:
    h = _tiles("m1","m2","m3","m4","m5","m6","m7","m8","m9","z1","z1","z1","z3","z3")
    result = _eval(h, win=Tile("z", 3), is_tsumo=True)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "混一色" in names


def test_chinitsu() -> None:
    h = _tiles("m1","m2","m3","m4","m5","m6","m7","m8","m9","m2","m2","m2","m5","m5")
    result = _eval(h, win=Tile("m", 5), is_tsumo=True)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "清一色" in names


def test_kokushi_yakuman() -> None:
    h = _tiles(*KOKUSHI_TILES, "z1")
    result = _eval(h, win=Tile("z", 1), is_tsumo=True)
    assert result is not None
    assert result.yakuman_multiple >= 1
    names = {n for n, _ in result.yaku}
    assert "国士無双" in names


def test_suuankou_concealed_tsumo() -> None:
    h = _tiles("m1","m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    result = _eval(h, win=Tile("p", 5), is_tsumo=True)
    assert result is not None
    assert result.yakuman_multiple >= 1


def test_suuankou_fails_on_ron_completing_triplet() -> None:
    # win by ron on m1 — completes the m1 triplet, no longer "concealed" for suuankou
    # need to construct: hand 13 + win = ron'd m1
    # so hand before win = remove one m1
    h_pre = _tiles("m1","m1","p2","p2","p2","s3","s3","s3","m9","m9","m9","p5","p5")
    result = _eval(h_pre + _tiles("m1"), win=Tile("m", 1), is_tsumo=False)
    # Either suuankou fails (3 concealed → sanankou+toitoi), or some other yaku is present.
    assert result is not None
    if result.yakuman_multiple > 0:
        # should be 0 since one triplet became open via ron
        names = {n for n, _ in result.yaku}
        assert "四暗刻" not in names


def test_ittsu() -> None:
    h = _tiles("m1","m2","m3","m4","m5","m6","m7","m8","m9","p2","p3","p4","s5","s5")
    result = _eval(h, win=Tile("s", 5), is_tsumo=True)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "一気通貫" in names


def test_sanshoku_doujun() -> None:
    h = _tiles("m1","m2","m3","p1","p2","p3","s1","s2","s3","m7","m8","m9","z3","z3")
    result = _eval(h, win=Tile("z", 3), is_tsumo=True)
    assert result is not None
    names = {n for n, _ in result.yaku}
    assert "三色同順" in names


def test_double_wind_yakuhai_counts_twice() -> None:
    # east round, east seat, east triplet → +2 han
    h = _tiles("m1","m2","m3","p4","p5","p6","s7","s8","s9","z1","z1","z1","s1","s1")
    result = _eval(h, win=Tile("s", 1), is_tsumo=True, seat_wind=1, round_wind=1)
    assert result is not None
    yakuhai_han = next((v for n, v in result.yaku if n == "役牌"), 0)
    assert yakuhai_han == 2


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items() if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f()
        print(f"  ✓ {n}")
    print(f"\n{len(fns)} tests passed")
