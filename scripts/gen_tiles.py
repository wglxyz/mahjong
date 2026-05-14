"""Generate placeholder SVG tiles for the Flutter client.

Output: 37 files at client_flutter/assets/tiles/
  m1..m9, p1..p9, s1..s9, z1..z7, m5r, p5r, s5r, back

The design follows traditional mahjong tile conventions:
  - m (萬): Chinese numeral + 萬 character
  - p (筒): N circle bosses in canonical arrangement
  - s (索): N vertical bamboo sticks; 1s is a stylised bird-bamboo
  - z (字): wind/dragon character; 白 is a framed blank, 發 green, 中 red

When real artwork arrives, replace the SVGs with the same filenames — the Flutter
client loads by code (e.g. `assets/tiles/m5.svg`) so nothing else changes.
"""
from __future__ import annotations
import os

OUT = "/root/avid/client_flutter/assets/tiles"

# tile dimensions (viewBox)
W, H = 100, 140
CX, CY = W / 2, H / 2

# palette
INK = "#3A2817"
RED = "#A82828"
GREEN = "#1E7A3A"
CREAM_TOP = "#FFF8E7"
CREAM_BOT = "#E8DCC0"
BORDER = "#B08D5E"
GOLD = "#D4A857"
BACK_TOP = "#2C5A4A"
BACK_BOT = "#143628"

NUMERALS = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
WINDS = {1: "東", 2: "南", 3: "西", 4: "北"}


def _frame(content: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <linearGradient id="cream" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{CREAM_TOP}"/>
      <stop offset="100%" stop-color="{CREAM_BOT}"/>
    </linearGradient>
    <linearGradient id="hl" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.55"/>
      <stop offset="25%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect x="3" y="3" width="{W-6}" height="{H-6}" rx="11" ry="11"
        fill="url(#cream)" stroke="{BORDER}" stroke-width="1.5"/>
  <rect x="5" y="5" width="{W-10}" height="{H-10}" rx="9" ry="9" fill="url(#hl)"/>
  {content}
</svg>
"""


def _tile_m(rank: int, red: bool = False) -> str:
    color = RED if red else INK
    numeral = NUMERALS[rank]
    body = f"""
  <text x="{CX}" y="55" font-family="'Songti SC','STSong','Noto Serif CJK SC','Source Han Serif SC',serif"
        font-size="50" font-weight="700" fill="{color}"
        text-anchor="middle" dominant-baseline="middle">{numeral}</text>
  <text x="{CX}" y="108" font-family="'Songti SC','STSong','Noto Serif CJK SC',serif"
        font-size="30" font-weight="700" fill="{color}"
        text-anchor="middle" dominant-baseline="middle">萬</text>
"""
    return _frame(body)


# canonical layouts for N pips, expressed as (dx, dy) offsets around (CX, CY)
_PIP_LAYOUTS = {
    1: [(0, 0)],
    2: [(0, -22), (0, 22)],
    3: [(-22, -22), (0, 0), (22, 22)],
    4: [(-18, -22), (18, -22), (-18, 22), (18, 22)],
    5: [(-22, -25), (22, -25), (0, 0), (-22, 25), (22, 25)],
    6: [(-22, -28), (22, -28), (-22, 0), (22, 0), (-22, 28), (22, 28)],
    7: [(-22, -32), (0, -32), (22, -32), (-22, -2), (22, -2), (-11, 28), (11, 28)],
    8: [(-22, -32), (0, -32), (22, -32), (-22, 0), (22, 0), (-22, 32), (0, 32), (22, 32)],
    9: [(-22, -30), (0, -30), (22, -30), (-22, 0), (0, 0), (22, 0), (-22, 30), (0, 30), (22, 30)],
}


def _tile_p(rank: int, red: bool = False) -> str:
    color = RED if red else INK
    pts = _PIP_LAYOUTS[rank]
    pip = ""
    for dx, dy in pts:
        # double-ring pattern for the iconic 筒 look
        pip += (
            f'<circle cx="{CX+dx}" cy="{CY+dy}" r="9.5" fill="{color}" stroke="{BORDER}" stroke-width="0.5"/>'
            f'<circle cx="{CX+dx}" cy="{CY+dy}" r="4" fill="{CREAM_TOP}"/>'
        )
    return _frame(pip)


def _tile_s(rank: int, red: bool = False) -> str:
    color = RED if red else GREEN
    if rank == 1:
        # stylised bamboo-stalk with leaves (placeholder for the bird)
        body = f"""
  <rect x="{CX-6}" y="{CY-32}" width="12" height="64" rx="3" fill="{color}"/>
  <ellipse cx="{CX-19}" cy="{CY-22}" rx="11" ry="5" fill="{color}"
           transform="rotate(-32 {CX-19} {CY-22})"/>
  <ellipse cx="{CX+19}" cy="{CY-10}" rx="11" ry="5" fill="{color}"
           transform="rotate(32 {CX+19} {CY-10})"/>
  <ellipse cx="{CX-19}" cy="{CY+12}" rx="11" ry="5" fill="{color}"
           transform="rotate(-32 {CX-19} {CY+12})"/>
  <ellipse cx="{CX+19}" cy="{CY+24}" rx="11" ry="5" fill="{color}"
           transform="rotate(32 {CX+19} {CY+24})"/>
"""
    else:
        body = ""
        for dx, dy in _PIP_LAYOUTS[rank]:
            x = CX + dx - 4
            y = CY + dy - 14
            body += (
                f'<rect x="{x}" y="{y}" width="8" height="28" rx="2.5" '
                f'fill="{color}" stroke="{BORDER}" stroke-width="0.4"/>'
            )
    return _frame(body)


def _tile_z(rank: int) -> str:
    if rank in (1, 2, 3, 4):
        ch = WINDS[rank]
        color = INK
        body = f"""
  <text x="{CX}" y="{CY+4}" font-family="'Songti SC','STSong','Noto Serif CJK SC',serif"
        font-size="62" font-weight="700" fill="{color}"
        text-anchor="middle" dominant-baseline="middle">{ch}</text>
"""
    elif rank == 5:
        # 白 — framed blank (traditional)
        body = f"""
  <rect x="{CX-28}" y="{CY-36}" width="56" height="72" rx="3"
        fill="none" stroke="{INK}" stroke-width="3.5"/>
  <rect x="{CX-22}" y="{CY-30}" width="44" height="60" rx="2"
        fill="none" stroke="{INK}" stroke-width="0.8" opacity="0.4"/>
"""
    elif rank == 6:
        # 發 — green
        body = f"""
  <text x="{CX}" y="{CY+4}" font-family="'Songti SC','STSong','Noto Serif CJK SC',serif"
        font-size="58" font-weight="700" fill="{GREEN}"
        text-anchor="middle" dominant-baseline="middle">發</text>
"""
    else:  # rank == 7, 中
        body = f"""
  <rect x="{CX-26}" y="{CY-32}" width="52" height="64" rx="3"
        fill="none" stroke="{RED}" stroke-width="1.5" opacity="0.0"/>
  <text x="{CX}" y="{CY+4}" font-family="'Songti SC','STSong','Noto Serif CJK SC',serif"
        font-size="62" font-weight="700" fill="{RED}"
        text-anchor="middle" dominant-baseline="middle">中</text>
"""
    return _frame(body)


def _tile_back() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <linearGradient id="back" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{BACK_TOP}"/>
      <stop offset="100%" stop-color="{BACK_BOT}"/>
    </linearGradient>
  </defs>
  <rect x="3" y="3" width="{W-6}" height="{H-6}" rx="11" fill="url(#back)"
        stroke="{BORDER}" stroke-width="1.5"/>
  <rect x="13" y="13" width="{W-26}" height="{H-26}" rx="7"
        fill="none" stroke="{GOLD}" stroke-width="1" opacity="0.5"/>
  <text x="{CX}" y="{CY+12}" font-family="'Songti SC','STSong',serif" font-size="38"
        fill="{GOLD}" opacity="0.6" text-anchor="middle">麻</text>
</svg>
"""


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for r in range(1, 10):
        open(f"{OUT}/m{r}.svg", "w").write(_tile_m(r))
        open(f"{OUT}/p{r}.svg", "w").write(_tile_p(r))
        open(f"{OUT}/s{r}.svg", "w").write(_tile_s(r))
    for suit, fn in (("m", _tile_m), ("p", _tile_p), ("s", _tile_s)):
        open(f"{OUT}/{suit}5r.svg", "w").write(fn(5, red=True))
    for r in range(1, 8):
        open(f"{OUT}/z{r}.svg", "w").write(_tile_z(r))
    open(f"{OUT}/back.svg", "w").write(_tile_back())
    print(f"wrote {len(os.listdir(OUT))} tile SVGs to {OUT}")


if __name__ == "__main__":
    main()
