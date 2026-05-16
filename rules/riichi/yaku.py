"""Yaku detection for riichi mahjong (C tier — 19 regular yaku + 14 yakuman).

Each yaku is a pure function (decomp, ctx) → han value (0 if not applicable).
`evaluate(decomps, ctx)` picks the highest-scoring decomposition and returns
(yaku_list, total_han, yakuman_multiple).

Conventions:
  - "concealed hand" = no group was formed via chi/pon/minkan (ankan keeps concealment).
  - For yakuman, we don't add dora.
  - Mutually-exclusive yaku (iipeiko/ryanpeikou, chanta/junchan, honitsu/chinitsu) handled in evaluate().
"""
from __future__ import annotations

from dataclasses import dataclass

from mahjong.tile import NUMERIC_SUITS, SUIT_Z
from rules.riichi.decompose import (
    GROUP_QUAD,
    GROUP_RUN,
    GROUP_TRIPLET,
    Decomposition,
    is_honor_code,
    is_terminal_code,
    is_terminal_or_honor_code,
)


@dataclass
class YakuContext:
    seat_wind: int = 1        # 1=E 2=S 3=W 4=N
    round_wind: int = 1
    is_tsumo: bool = False
    is_riichi: bool = False
    is_double_riichi: bool = False
    is_ippatsu: bool = False
    is_rinshan: bool = False  # win on kan replacement draw
    is_chankan: bool = False  # ron on shouminkan upgrade
    is_haitei: bool = False   # tsumo on last wall tile
    is_houtei: bool = False   # ron on the final discard
    is_tenhou: bool = False
    is_chiihou: bool = False
    dora_count: int = 0
    ura_dora_count: int = 0
    red_dora_count: int = 0


def _is_concealed(decomp: Decomposition) -> bool:
    return all(not g.from_call for g in decomp.groups)


def _all_tiles(decomp: Decomposition) -> list[str]:
    return [t for g in decomp.groups for t in g.tiles]


# ──────────────────────────────────────────────────────────────────────────
# 1-han yaku
# ──────────────────────────────────────────────────────────────────────────
def yaku_riichi(d, ctx):
    return 1 if ctx.is_riichi and not ctx.is_double_riichi else 0


def yaku_double_riichi(d, ctx):
    return 2 if ctx.is_double_riichi else 0


def yaku_ippatsu(d, ctx):
    return 1 if ctx.is_ippatsu else 0


def yaku_menzen_tsumo(d, ctx):
    if not ctx.is_tsumo:
        return 0
    if not _is_concealed(d):
        return 0
    return 1


def yaku_pinfu(d, ctx):
    if d.structure != "standard":
        return 0
    if not _is_concealed(d):
        return 0
    for g in d.melds:
        if g.kind != GROUP_RUN:
            return 0
    pair_code = d.pair.tiles[0]
    if pair_code in ("z5", "z6", "z7"):
        return 0
    if pair_code == f"z{ctx.seat_wind}":
        return 0
    if pair_code == f"z{ctx.round_wind}":
        return 0
    win = d.winning_tile_code
    for r in d.melds:
        if win not in r.tiles:
            continue
        ranks = sorted(int(t[1:]) for t in r.tiles)
        wr = int(win[1:])
        r0, _, r2 = ranks
        if wr == r0 and r0 <= 6:
            return 1
        if wr == r2 and r0 >= 2:
            return 1
    return 0


def yaku_iipeiko(d, ctx):
    if d.structure != "standard":
        return 0
    if not _is_concealed(d):
        return 0
    runs = [g.tiles for g in d.melds if g.kind == GROUP_RUN]
    counts: dict[tuple, int] = {}
    for r in runs:
        counts[r] = counts.get(r, 0) + 1
    pairs = sum(v // 2 for v in counts.values())
    if pairs >= 2:
        return 0  # ryanpeikou
    return 1 if pairs == 1 else 0


def yaku_tanyao(d, ctx):
    if d.structure == "kokushi":
        return 0
    for t in _all_tiles(d):
        if is_terminal_or_honor_code(t):
            return 0
    return 1


def yaku_yakuhai(d, ctx):
    if d.structure != "standard":
        return 0
    han = 0
    seat_code = f"z{ctx.seat_wind}"
    round_code = f"z{ctx.round_wind}"
    for g in d.melds:
        if g.kind not in (GROUP_TRIPLET, GROUP_QUAD):
            continue
        code = g.tiles[0]
        if code in ("z5", "z6", "z7"):
            han += 1
        if code == seat_code:
            han += 1
        if code == round_code and round_code != seat_code:
            han += 1
        elif code == round_code and round_code == seat_code:
            han += 1   # double-wind: count second role too
    return han


def yaku_rinshan(d, ctx):
    return 1 if ctx.is_rinshan else 0


def yaku_chankan(d, ctx):
    return 1 if ctx.is_chankan else 0


def yaku_haitei(d, ctx):
    return 1 if ctx.is_haitei else 0


def yaku_houtei(d, ctx):
    return 1 if ctx.is_houtei else 0


# ──────────────────────────────────────────────────────────────────────────
# 2-han yaku
# ──────────────────────────────────────────────────────────────────────────
def yaku_sanshoku_doujun(d, ctx):
    if d.structure != "standard":
        return 0
    runs = [g for g in d.melds if g.kind == GROUP_RUN]
    by_ranks: dict[tuple, set] = {}
    for r in runs:
        if r.tiles[0][0] in NUMERIC_SUITS:
            ranks = tuple(int(t[1:]) for t in r.tiles)
            by_ranks.setdefault(ranks, set()).add(r.tiles[0][0])
    for suits in by_ranks.values():
        if suits == set(NUMERIC_SUITS):
            return 2 if _is_concealed(d) else 1
    return 0


def yaku_ittsu(d, ctx):
    if d.structure != "standard":
        return 0
    runs = {g.tiles for g in d.melds if g.kind == GROUP_RUN}
    for suit in NUMERIC_SUITS:
        ittsu_set = {
            (f"{suit}1", f"{suit}2", f"{suit}3"),
            (f"{suit}4", f"{suit}5", f"{suit}6"),
            (f"{suit}7", f"{suit}8", f"{suit}9"),
        }
        if ittsu_set.issubset(runs):
            return 2 if _is_concealed(d) else 1
    return 0


def yaku_chanta(d, ctx):
    """Every group contains a terminal-or-honor. Excludes pure-honor (honroutou) and
    junchan (terminal-only)."""
    if d.structure != "standard":
        return 0
    for g in d.groups:
        if not any(is_terminal_or_honor_code(t) for t in g.tiles):
            return 0
    # exclude junchan (no honors anywhere)
    has_honor = any(is_honor_code(t) for t in _all_tiles(d))
    if not has_honor:
        return 0
    # exclude when there are no runs (might be honroutou)
    has_run = any(g.kind == GROUP_RUN for g in d.melds)
    if not has_run:
        return 0
    return 2 if _is_concealed(d) else 1


def yaku_chiitoitsu(d, ctx):
    return 2 if d.structure == "chiitoitsu" else 0


def yaku_toitoi(d, ctx):
    if d.structure != "standard":
        return 0
    for g in d.melds:
        if g.kind not in (GROUP_TRIPLET, GROUP_QUAD):
            return 0
    return 2


def yaku_sanankou(d, ctx):
    """3 concealed triplets/quads. If winning tile completes a triplet via ron, that
    triplet doesn't count as concealed."""
    if d.structure != "standard":
        return 0
    count = 0
    for g in d.melds:
        if g.kind not in (GROUP_TRIPLET, GROUP_QUAD):
            continue
        if not g.concealed:
            continue
        if not ctx.is_tsumo and d.winning_tile_code == g.tiles[0]:
            continue  # ron'd this triplet → counts as open for sanankou
        count += 1
    return 2 if count == 3 else 0


def yaku_sanshoku_doukou(d, ctx):
    if d.structure != "standard":
        return 0
    trips = [g for g in d.melds if g.kind in (GROUP_TRIPLET, GROUP_QUAD)]
    by_rank: dict[str, set] = {}
    for t in trips:
        if t.tiles[0][0] in NUMERIC_SUITS:
            r = t.tiles[0][1:]
            by_rank.setdefault(r, set()).add(t.tiles[0][0])
    for suits in by_rank.values():
        if suits == set(NUMERIC_SUITS):
            return 2
    return 0


def yaku_sankantsu(d, ctx):
    if d.structure != "standard":
        return 0
    quads = sum(1 for g in d.melds if g.kind == GROUP_QUAD)
    return 2 if quads == 3 else 0


def yaku_honroutou(d, ctx):
    if d.structure == "kokushi":
        return 0
    for t in _all_tiles(d):
        if not is_terminal_or_honor_code(t):
            return 0
    return 2


def yaku_shousangen(d, ctx):
    if d.structure != "standard":
        return 0
    dragon_trips = sum(
        1
        for g in d.melds
        if g.kind in (GROUP_TRIPLET, GROUP_QUAD) and g.tiles[0] in ("z5", "z6", "z7")
    )
    if dragon_trips != 2:
        return 0
    if d.pair is None or d.pair.tiles[0] not in ("z5", "z6", "z7"):
        return 0
    return 2


def yaku_ryanpeikou(d, ctx):
    if d.structure != "standard":
        return 0
    if not _is_concealed(d):
        return 0
    runs = [g.tiles for g in d.melds if g.kind == GROUP_RUN]
    counts: dict[tuple, int] = {}
    for r in runs:
        counts[r] = counts.get(r, 0) + 1
    pairs = sum(v // 2 for v in counts.values())
    return 3 if pairs == 2 else 0


# ──────────────────────────────────────────────────────────────────────────
# 3+ han
# ──────────────────────────────────────────────────────────────────────────
def yaku_junchan(d, ctx):
    if d.structure != "standard":
        return 0
    for g in d.groups:
        if not any(is_terminal_code(t) for t in g.tiles):
            return 0
        if any(is_honor_code(t) for t in g.tiles):
            return 0
    has_run = any(g.kind == GROUP_RUN for g in d.melds)
    if not has_run:
        return 0   # otherwise this is chinroutou
    return 3 if _is_concealed(d) else 2


def yaku_honitsu(d, ctx):
    if d.structure == "kokushi":
        return 0
    suits = {t[0] for t in _all_tiles(d)}
    numeric = suits & set(NUMERIC_SUITS)
    if len(numeric) != 1:
        return 0
    if SUIT_Z not in suits:
        return 0     # pure-numeric = chinitsu, handled separately
    return 3 if _is_concealed(d) else 2


def yaku_chinitsu(d, ctx):
    if d.structure == "kokushi":
        return 0
    suits = {t[0] for t in _all_tiles(d)}
    if len(suits) == 1 and next(iter(suits)) in NUMERIC_SUITS:
        return 6 if _is_concealed(d) else 5
    return 0


# ──────────────────────────────────────────────────────────────────────────
# Yakuman (count as 13 han equivalent; multiple yakuman stack)
# ──────────────────────────────────────────────────────────────────────────
def yakuman_kokushi(d, ctx):
    if d.structure != "kokushi":
        return 0
    # 13-wait variant: the player held all 13 unique terminals/honors and the win
    # completed the duplicate (pair). The pair group's code matches the winning tile.
    if d.pair is not None and d.pair.tiles[0] == d.winning_tile_code:
        return 26  # double yakuman
    return 13


def yakuman_suuankou(d, ctx):
    if d.structure != "standard":
        return 0
    if not _is_concealed(d):
        return 0
    trips = [g for g in d.melds if g.kind in (GROUP_TRIPLET, GROUP_QUAD)]
    if len(trips) != 4:
        return 0
    if not ctx.is_tsumo:
        for t in trips:
            if d.winning_tile_code == t.tiles[0]:
                return 0
    return 13


def yakuman_daisangen(d, ctx):
    if d.structure != "standard":
        return 0
    dragons = sum(
        1
        for g in d.melds
        if g.kind in (GROUP_TRIPLET, GROUP_QUAD) and g.tiles[0] in ("z5", "z6", "z7")
    )
    return 13 if dragons == 3 else 0


def yakuman_tsuuiisou(d, ctx):
    if d.structure == "kokushi":
        return 0
    for t in _all_tiles(d):
        if not is_honor_code(t):
            return 0
    return 13


_GREEN = {"s2", "s3", "s4", "s6", "s8", "z6"}


def yakuman_ryuuiisou(d, ctx):
    if d.structure == "kokushi":
        return 0
    for t in _all_tiles(d):
        if t not in _GREEN:
            return 0
    return 13


def yakuman_chinroutou(d, ctx):
    if d.structure != "standard":
        return 0
    for t in _all_tiles(d):
        if not is_terminal_code(t):
            return 0
    return 13


def yakuman_suukantsu(d, ctx):
    if d.structure != "standard":
        return 0
    quads = sum(1 for g in d.melds if g.kind == GROUP_QUAD)
    return 13 if quads == 4 else 0


def yakuman_shousuushii(d, ctx):
    if d.structure != "standard":
        return 0
    wind_trips = sum(
        1
        for g in d.melds
        if g.kind in (GROUP_TRIPLET, GROUP_QUAD) and g.tiles[0] in ("z1", "z2", "z3", "z4")
    )
    if wind_trips != 3:
        return 0
    if d.pair is None or d.pair.tiles[0] not in ("z1", "z2", "z3", "z4"):
        return 0
    return 13


def yakuman_daisuushii(d, ctx):
    if d.structure != "standard":
        return 0
    wind_trips = sum(
        1
        for g in d.melds
        if g.kind in (GROUP_TRIPLET, GROUP_QUAD) and g.tiles[0] in ("z1", "z2", "z3", "z4")
    )
    return 13 if wind_trips == 4 else 0


def yakuman_chuuren(d, ctx):
    """9 gates: concealed, single numeric suit, count pattern 3-1-1-1-1-1-1-1-3 + 1 extra.

    Pure 9-wait variant (the pre-win 13-tile hand is exactly 1112345678999) scores
    double yakuman.
    """
    if d.structure != "standard":
        return 0
    if not _is_concealed(d):
        return 0
    suits = {t[0] for t in _all_tiles(d)}
    if len(suits) != 1:
        return 0
    suit = next(iter(suits))
    if suit not in NUMERIC_SUITS:
        return 0
    counts = [0] * 10
    for t in _all_tiles(d):
        counts[int(t[1:])] += 1
    base = [0, 3, 1, 1, 1, 1, 1, 1, 1, 3]
    diffs = [counts[i] - base[i] for i in range(1, 10)]
    if sum(diffs) != 1:
        return 0
    if any(diff < 0 for diff in diffs):
        return 0
    # pure 9-wait: removing the winning tile yields exactly the base pattern
    wr = int(d.winning_tile_code[1:])
    pre = list(counts)
    pre[wr] -= 1
    if pre[1:10] == base[1:]:
        return 26  # double yakuman
    return 13


def yakuman_tenhou(d, ctx):
    return 13 if ctx.is_tenhou else 0


def yakuman_chiihou(d, ctx):
    return 13 if ctx.is_chiihou else 0


# ──────────────────────────────────────────────────────────────────────────
# Aggregation
# ──────────────────────────────────────────────────────────────────────────
_REGULAR_YAKU = [
    ("立直", yaku_riichi),
    ("両立直", yaku_double_riichi),
    ("一発", yaku_ippatsu),
    ("門前清自摸和", yaku_menzen_tsumo),
    ("平和", yaku_pinfu),
    ("断幺九", yaku_tanyao),
    ("役牌", yaku_yakuhai),
    ("一盃口", yaku_iipeiko),
    ("嶺上開花", yaku_rinshan),
    ("槍槓", yaku_chankan),
    ("海底摸月", yaku_haitei),
    ("河底撈魚", yaku_houtei),
    ("三色同順", yaku_sanshoku_doujun),
    ("一気通貫", yaku_ittsu),
    ("混全帯幺九", yaku_chanta),
    ("七対子", yaku_chiitoitsu),
    ("対々和", yaku_toitoi),
    ("三暗刻", yaku_sanankou),
    ("三色同刻", yaku_sanshoku_doukou),
    ("三槓子", yaku_sankantsu),
    ("混老頭", yaku_honroutou),
    ("小三元", yaku_shousangen),
    ("二盃口", yaku_ryanpeikou),
    ("純全帯幺九", yaku_junchan),
    ("混一色", yaku_honitsu),
    ("清一色", yaku_chinitsu),
]

_YAKUMAN = [
    ("国士無双", yakuman_kokushi),
    ("四暗刻", yakuman_suuankou),
    ("大三元", yakuman_daisangen),
    ("字一色", yakuman_tsuuiisou),
    ("緑一色", yakuman_ryuuiisou),
    ("清老頭", yakuman_chinroutou),
    ("四槓子", yakuman_suukantsu),
    ("小四喜", yakuman_shousuushii),
    ("大四喜", yakuman_daisuushii),
    ("九蓮宝燈", yakuman_chuuren),
    ("天和", yakuman_tenhou),
    ("地和", yakuman_chiihou),
]


@dataclass
class YakuResult:
    yaku: list[tuple[str, int]]  # (name, han)
    total_han: int
    yakuman_multiple: int        # >0 if yakuman; multiplied yakuman if stacked
    decomp: Decomposition


def evaluate(decomps: list[Decomposition], ctx: YakuContext) -> YakuResult | None:
    """From every valid decomposition, return the highest-scoring yaku set.

    Returns None if no decomposition yields any yaku (i.e. yakuless win — not allowed
    in riichi). The caller (Ruleset.is_winning_hand) should treat None as "not a legal win".
    """
    best: YakuResult | None = None
    for d in decomps:
        # yakuman first. Each yakuman fn returns 13 (single) or 26 (double); stack as multiples.
        ym_list: list[tuple[str, int]] = []
        ym_multiple = 0
        for name, fn in _YAKUMAN:
            v = fn(d, ctx)
            if v:
                ym_list.append((name, v))
                ym_multiple += v // 13
        if ym_multiple:
            res = YakuResult(
                yaku=ym_list,
                total_han=ym_multiple * 13,
                yakuman_multiple=ym_multiple,
                decomp=d,
            )
            if best is None or res.total_han > best.total_han:
                best = res
            continue

        # regular yaku
        yaku_list: list[tuple[str, int]] = []
        han = 0
        for name, fn in _REGULAR_YAKU:
            v = fn(d, ctx)
            if v:
                yaku_list.append((name, v))
                han += v

        if han == 0:
            continue   # this decomposition has no yaku; can't win on it (yakuless)

        # dora doesn't add yaku, but adds han once at least one real yaku exists
        if ctx.dora_count:
            yaku_list.append(("ドラ", ctx.dora_count))
            han += ctx.dora_count
        if ctx.red_dora_count:
            yaku_list.append(("赤ドラ", ctx.red_dora_count))
            han += ctx.red_dora_count
        if ctx.ura_dora_count and ctx.is_riichi:
            yaku_list.append(("裏ドラ", ctx.ura_dora_count))
            han += ctx.ura_dora_count

        res = YakuResult(yaku=yaku_list, total_han=han, yakuman_multiple=0, decomp=d)
        if best is None or res.total_han > best.total_han:
            best = res

    return best
