"""Riichi scoring: han + fu → base points → per-seat payouts.

Standard table (non-dealer / dealer ron in parens):
  base = fu × 2^(han + 2), capped at 2000
  Han 5: mangan         base 2000 → 8000 / 12000
  Han 6-7: haneman      base 3000 → 12000 / 18000
  Han 8-10: baiman      base 4000 → 16000 / 24000
  Han 11-12: sanbaiman  base 6000 → 24000 / 36000
  Han 13+: yakuman      base 8000 → 32000 / 48000  (kazoe-yakuman)
  Stacked yakuman: N × yakuman base

Payouts round up to the nearest 100 per payer.
"""
from __future__ import annotations
import math

from rules.riichi.decompose import (
    GROUP_QUAD,
    GROUP_RUN,
    GROUP_TRIPLET,
    Decomposition,
    is_terminal_or_honor_code,
)
from rules.riichi.yaku import YakuContext, YakuResult


def _is_concealed(decomp: Decomposition) -> bool:
    return all(not g.from_call for g in decomp.groups)


def calculate_fu(decomp: Decomposition, ctx: YakuContext, is_pinfu: bool) -> int:
    if decomp.structure == "chiitoitsu":
        return 25
    if decomp.structure == "kokushi":
        return 30  # ignored — yakuman is base-fixed
    if is_pinfu:
        return 20 if ctx.is_tsumo else 30

    fu = 20
    if ctx.is_tsumo:
        fu += 2
    if not ctx.is_tsumo and _is_concealed(decomp):
        fu += 10

    for g in decomp.melds:
        fu += _meld_fu(g, decomp, ctx)

    pair_code = decomp.pair.tiles[0] if decomp.pair else ""
    if pair_code in ("z5", "z6", "z7"):
        fu += 2
    if pair_code == f"z{ctx.seat_wind}":
        fu += 2
    if pair_code == f"z{ctx.round_wind}":
        fu += 2  # may double-count when seat==round; intentional

    fu += _wait_fu(decomp)

    # round up to next 10
    return ((fu + 9) // 10) * 10


def _meld_fu(g, decomp: Decomposition, ctx: YakuContext) -> int:
    if g.kind == GROUP_RUN:
        return 0
    simple = not is_terminal_or_honor_code(g.tiles[0])
    if g.kind == GROUP_TRIPLET:
        base = 2 if simple else 4
        # ron'd triplet (winning tile completes it from someone else's discard) counts as open
        ron_open = (not ctx.is_tsumo) and decomp.winning_tile_code == g.tiles[0]
        if g.concealed and not ron_open:
            base *= 2
        return base
    if g.kind == GROUP_QUAD:
        base = 8 if simple else 16
        if g.concealed:
            base *= 2
        return base
    return 0


def _wait_fu(decomp: Decomposition) -> int:
    """Best wait fu: prefers kanchan/penchan/tanki (+2) over ryanmen/shanpon (+0)."""
    win = decomp.winning_tile_code
    candidates: list[int] = []
    if decomp.pair and decomp.pair.tiles[0] == win:
        candidates.append(2)  # tanki
    for g in decomp.melds:
        if win not in g.tiles:
            continue
        if g.kind == GROUP_RUN:
            ranks = sorted(int(t[1:]) for t in g.tiles)
            wr = int(win[1:])
            r0 = ranks[0]
            if wr == ranks[1]:
                candidates.append(2)               # kanchan
            elif (wr == 3 and r0 == 1) or (wr == 7 and r0 == 7):
                candidates.append(2)               # penchan
            else:
                candidates.append(0)               # ryanmen
        elif g.kind in (GROUP_TRIPLET, GROUP_QUAD):
            candidates.append(0)                   # shanpon
    return max(candidates) if candidates else 0


def base_points(han: int, fu: int, yakuman_multiple: int) -> int:
    if yakuman_multiple > 0:
        return 8000 * yakuman_multiple
    if han >= 13:
        return 8000  # kazoe yakuman
    if han >= 11:
        return 6000  # sanbaiman
    if han >= 8:
        return 4000  # baiman
    if han >= 6:
        return 3000  # haneman
    if han >= 5:
        return 2000  # mangan
    return min(fu * (2 ** (han + 2)), 2000)


def _ceil100(x: int) -> int:
    return int(math.ceil(x / 100.0)) * 100


def calculate_payouts(
    base: int,
    is_tsumo: bool,
    winner_seat: int,
    loser_seat: int | None,
    dealer_seat: int,
    seats: int = 4,
) -> dict[int, int]:
    payouts = {s: 0 for s in range(seats)}
    is_dealer_win = winner_seat == dealer_seat
    if is_tsumo:
        for s in range(seats):
            if s == winner_seat:
                continue
            if is_dealer_win:
                pay = _ceil100(2 * base)
            else:
                pay = _ceil100(2 * base) if s == dealer_seat else _ceil100(base)
            payouts[s] -= pay
            payouts[winner_seat] += pay
    else:
        assert loser_seat is not None
        pay = _ceil100(6 * base if is_dealer_win else 4 * base)
        payouts[loser_seat] -= pay
        payouts[winner_seat] += pay
    return payouts


def score(
    yaku_result: YakuResult,
    ctx: YakuContext,
    winner_seat: int,
    loser_seat: int | None,
    dealer_seat: int,
    seats: int = 4,
) -> tuple[dict[int, int], int, int]:
    """Return (per-seat deltas, fu used, base points)."""
    is_pinfu = any(name == "平和" for name, _ in yaku_result.yaku)
    fu = calculate_fu(yaku_result.decomp, ctx, is_pinfu)
    base = base_points(yaku_result.total_han, fu, yaku_result.yakuman_multiple)
    deltas = calculate_payouts(base, ctx.is_tsumo, winner_seat, loser_seat, dealer_seat, seats)
    return deltas, fu, base
