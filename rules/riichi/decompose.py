"""Hand decomposition for riichi yaku detection.

Given a hand (concealed tiles + already-declared melds + winning tile), enumerate every
valid way the 14 tiles can be partitioned into a winning shape. Three shapes exist:

  - standard:    4 melds (run/triplet/quad) + 1 pair
  - chiitoitsu:  7 distinct pairs (concealed hand only)
  - kokushi:     all 13 unique terminals/honors + one duplicate (concealed hand only)

A single hand may have multiple valid standard decompositions (e.g. 234234m can be
two 234m runs OR a 222m triplet would-need... well let's say genuine cases like
11122233344455 has multiple cuts). Yaku judgement picks the decomposition with the
highest han, so we return ALL of them.

We work in "code space" — tile.code like "m5" or "z3" — losing entity identity.
Yaku functions only need rank/suit; entity-aware concerns (red dora) are passed
through the winning_tile reference and a separate red-tile count.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from mahjong.meld import ANKAN, CHI, MINKAN, PON, SHOUMINKAN, Meld
from mahjong.tile import NUMERIC_SUITS, SUIT_Z, Tile

# ---- group / decomposition data --------------------------------------------
GROUP_RUN = "run"
GROUP_TRIPLET = "triplet"
GROUP_QUAD = "quad"
GROUP_PAIR = "pair"
GROUP_KOKUSHI_SINGLE = "kokushi_single"  # one of the 13 unique terminals/honors in kokushi


@dataclass(frozen=True)
class Group:
    kind: str
    tiles: tuple[str, ...]   # tile codes ("m5", "z3", ...) — order canonical for runs (ascending)
    concealed: bool          # True if this group is concealed from opponents (closed)
    from_call: bool = False  # True if this group was formed by chi/pon/minkan (NOT ankan)


@dataclass(frozen=True)
class Decomposition:
    structure: str           # "standard" | "chiitoitsu" | "kokushi"
    groups: tuple[Group, ...]
    pair: Group | None       # the pair group for standard/kokushi (None for chiitoitsu — every group IS a pair)
    melds: tuple[Group, ...] # non-pair groups (empty for chiitoitsu)
    winning_tile_code: str
    winning_tile_red: bool


# ---- public entrypoint -----------------------------------------------------
KOKUSHI_TILES = ("m1", "m9", "p1", "p9", "s1", "s9", "z1", "z2", "z3", "z4", "z5", "z6", "z7")


def all_decompositions(
    concealed_tiles: list[Tile],
    declared_melds: list[Meld],
    winning_tile: Tile,
) -> list[Decomposition]:
    """Return every valid winning decomposition. Empty list ⇒ not a winning hand."""
    concealed_codes = [t.code for t in concealed_tiles]
    declared_groups = [_meld_to_group(m) for m in declared_melds]

    results: list[Decomposition] = []
    results.extend(_kokushi(concealed_codes, declared_groups, winning_tile))
    results.extend(_chiitoitsu(concealed_codes, declared_groups, winning_tile))
    results.extend(_standard(concealed_codes, declared_groups, winning_tile))
    return results


def is_winning(
    concealed_tiles: list[Tile],
    declared_melds: list[Meld],
    winning_tile: Tile,
) -> bool:
    """Cheap True/False win check — for legal_after_draw etc. where we don't need full yaku."""
    return bool(all_decompositions(concealed_tiles, declared_melds, winning_tile))


# ---- meld → group --------------------------------------------------------
def _meld_to_group(meld: Meld) -> Group:
    codes = tuple(sorted(t.code for t in meld.tiles))
    if meld.meld_type == CHI:
        return Group(GROUP_RUN, codes, concealed=False, from_call=True)
    if meld.meld_type == PON:
        return Group(GROUP_TRIPLET, codes, concealed=False, from_call=True)
    if meld.meld_type in (MINKAN, SHOUMINKAN):
        return Group(GROUP_QUAD, codes, concealed=False, from_call=True)
    if meld.meld_type == ANKAN:
        return Group(GROUP_QUAD, codes, concealed=True, from_call=False)
    raise ValueError(f"unknown meld type: {meld.meld_type}")


# ---- kokushi --------------------------------------------------------------
def _kokushi(
    concealed_codes: list[str],
    declared_groups: list[Group],
    winning_tile: Tile,
) -> list[Decomposition]:
    if declared_groups:
        return []
    if len(concealed_codes) != 14:
        return []
    counts: dict[str, int] = {}
    for c in concealed_codes:
        counts[c] = counts.get(c, 0) + 1
    if any(c not in KOKUSHI_TILES for c in counts):
        return []
    if not all(counts.get(t, 0) >= 1 for t in KOKUSHI_TILES):
        return []
    pair_codes = [t for t in KOKUSHI_TILES if counts[t] == 2]
    if len(pair_codes) != 1:
        return []
    pair_code = pair_codes[0]
    groups: list[Group] = []
    pair: Group | None = None
    for t in KOKUSHI_TILES:
        if t == pair_code:
            pair = Group(GROUP_PAIR, (t, t), concealed=True)
            groups.append(pair)
        else:
            groups.append(Group(GROUP_KOKUSHI_SINGLE, (t,), concealed=True))
    return [
        Decomposition(
            structure="kokushi",
            groups=tuple(groups),
            pair=pair,
            melds=(),
            winning_tile_code=winning_tile.code,
            winning_tile_red=winning_tile.red,
        )
    ]


# ---- chiitoitsu -----------------------------------------------------------
def _chiitoitsu(
    concealed_codes: list[str],
    declared_groups: list[Group],
    winning_tile: Tile,
) -> list[Decomposition]:
    if declared_groups:
        return []
    if len(concealed_codes) != 14:
        return []
    counts: dict[str, int] = {}
    for c in concealed_codes:
        counts[c] = counts.get(c, 0) + 1
    if len(counts) != 7 or not all(v == 2 for v in counts.values()):
        return []
    groups = tuple(
        Group(GROUP_PAIR, (c, c), concealed=True) for c in sorted(counts.keys())
    )
    return [
        Decomposition(
            structure="chiitoitsu",
            groups=groups,
            pair=None,
            melds=(),
            winning_tile_code=winning_tile.code,
            winning_tile_red=winning_tile.red,
        )
    ]


# ---- standard 4 melds + 1 pair --------------------------------------------
def _standard(
    concealed_codes: list[str],
    declared_groups: list[Group],
    winning_tile: Tile,
) -> list[Decomposition]:
    needed_from_hand = 4 - len(declared_groups)
    if needed_from_hand < 0:
        return []
    expected = needed_from_hand * 3 + 2
    if len(concealed_codes) != expected:
        return []

    counts: dict[str, int] = {}
    for c in concealed_codes:
        counts[c] = counts.get(c, 0) + 1

    out: list[Decomposition] = []
    for pair_code in sorted(counts.keys()):
        if counts[pair_code] < 2:
            continue
        counts[pair_code] -= 2
        for cut in _decompose_melds(counts, needed_from_hand):
            pair_group = Group(GROUP_PAIR, (pair_code, pair_code), concealed=True)
            hand_melds = tuple(
                Group(kind, tiles, concealed=True) for (kind, tiles) in cut
            )
            all_melds = hand_melds + tuple(declared_groups)
            out.append(
                Decomposition(
                    structure="standard",
                    groups=(pair_group,) + all_melds,
                    pair=pair_group,
                    melds=all_melds,
                    winning_tile_code=winning_tile.code,
                    winning_tile_red=winning_tile.red,
                )
            )
        counts[pair_code] += 2

    return out


def _decompose_melds(
    counts: dict[str, int], n_needed: int
) -> Iterator[list[tuple[str, tuple[str, str, str]]]]:
    """Yield every way to cut `counts` into exactly `n_needed` runs/triplets.

    Operates by always consuming the lexicographically-smallest remaining tile, which makes
    enumeration finite and avoids generating duplicates.
    """
    if n_needed == 0:
        if all(v == 0 for v in counts.values()):
            yield []
        return
    keys = sorted(k for k, v in counts.items() if v > 0)
    if not keys:
        return
    k = keys[0]
    suit, rank = k[0], int(k[1:])

    # triplet
    if counts[k] >= 3:
        counts[k] -= 3
        for rest in _decompose_melds(counts, n_needed - 1):
            yield [(GROUP_TRIPLET, (k, k, k))] + rest
        counts[k] += 3

    # sequence (numeric suits only, starting tile rank ≤ 7)
    if suit in NUMERIC_SUITS and rank <= 7:
        k2 = f"{suit}{rank + 1}"
        k3 = f"{suit}{rank + 2}"
        if counts.get(k2, 0) >= 1 and counts.get(k3, 0) >= 1:
            counts[k] -= 1
            counts[k2] -= 1
            counts[k3] -= 1
            for rest in _decompose_melds(counts, n_needed - 1):
                yield [(GROUP_RUN, (k, k2, k3))] + rest
            counts[k] += 1
            counts[k2] += 1
            counts[k3] += 1


# ---- helpers used by yaku code --------------------------------------------
def is_terminal_or_honor_code(code: str) -> bool:
    if code[0] == SUIT_Z:
        return True
    return code[1:] in ("1", "9")


def is_honor_code(code: str) -> bool:
    return code[0] == SUIT_Z


def is_terminal_code(code: str) -> bool:
    return code[0] in NUMERIC_SUITS and code[1:] in ("1", "9")


def all_tile_codes_in(decomp: Decomposition) -> list[str]:
    out: list[str] = []
    for g in decomp.groups:
        out.extend(g.tiles)
    return out
