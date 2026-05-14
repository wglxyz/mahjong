# TODO

Outstanding items, grouped by layer. Items marked `[doc]` are already
documented as known simplifications in the corresponding module's docstring.

## L1 — core engine

- [ ] **Async ActionProvider** alternative. Today `choose()` is sync and the WS
      provider bridges via a thread. An `AsyncActionProvider` variant would
      avoid the thread-and-queue dance for I/O-bound providers (network AIs,
      remote players over slow links).
- [ ] **Event-log replay**. We have seedable RNG but no recorded action log,
      so we can't replay a game deterministically from events alone (you'd have
      to rerun with the same seed AND providers).
- [ ] **Snapshot deltas**. Server currently sends a full snapshot before each
      decision. Fine for one client; a delta protocol would scale to spectators.
- [ ] **Per-seat state views**. `core` exposes the full state; the per-seat
      filtering only happens in `server/serialize.py`. If an in-process
      `ActionProvider` peeked at state, it'd see hidden info. Not a problem for
      Avid's AIs (they cheat anyway), but worth flagging.

## L2 — mahjong abstract game

- [ ] **Chankan response window**. `[doc]` Currently shouminkan declarations
      go straight to a rinshan draw; the rules permit opponents to ron on the
      added tile. Would require teaching the abstract game a "kan declared,
      pending response" intermediate phase.
- [ ] **Per-tile riichi flag in protocol**. The riichi discard should render
      sideways in the discard pile (and the rotated-tile detail in real
      tile-pile rendering). The event has `riichi: bool` but `TileView` doesn't
      carry it; a `was_riichi_discard` bit would close the gap.
- [ ] **Multi-hand sessions**. Today a session plays one hand and stops. East
      round (or East+South) needs: rotate dealer (or stay on dealer win), reset
      wall, carry over riichi sticks and honba, end after configured rounds.

## L3 — riichi ruleset

All listed at the top of `rules/riichi/ruleset.py` too. `[doc]`

- [ ] **Furiten**. A player who has previously discarded one of their winning
      tiles cannot ron. The check itself is easy (compare winning tile to own
      discards); plumbing the state through `ctx` is the work.
- [ ] **Double riichi**. Declare on the very first turn with no intervening
      calls → 2 han instead of 1. We have the flag in `YakuContext` but never
      set it.
- [ ] **Tenhou / chiihou**. Dealer tsumo on opening turn / non-dealer tsumo on
      the first uninterrupted go-around. Functions exist in `yaku.py`; only
      missing detection in `observe()`.
- [ ] **Nagashi mangan**. All-terminal/honor discard pile at drawn game scores
      as mangan. New event branch on `HandDrawn`.
- [ ] **Kan dora / ura dora**. Reveals on kan declarations and on riichi wins.
      Indicators are managed in `observe()`; ura dora needs a separate pile
      flipped only on winners with riichi.
- [ ] **Double ron / triple ron**. Atama-hane (head-bump, closest seat wins) is
      what we implement; standard JPN allows double ron, with payout split.
- [ ] **Double yakuman**. 13-wait kokushi and 9-wait chuuren are commonly
      double yakuman. Currently flat 13-han / single yakuman.
- [ ] **Special draws**: nine-terminals abort (kyuushuu kyuuhai), four-winds
      restart, four-kans abort, four-riichi abort, triple-ron abort.

## server/

- [ ] **Multi-client sessions**. One WS connection ⇒ one solo game. No lobby,
      no table assignment, no 4-human tables.
- [ ] **Authentication / identity**. No user accounts; anyone who can reach the
      port joins as seat 0.
- [ ] **Reconnect recovery**. `request_snapshot` works mid-game but the engine
      lives in memory only; if the WS drops mid-decision the session ends.
      Real reconnect needs session persistence + auth.
- [ ] **deadline_ms enforcement**. We carry `deadline_ms` in `DecisionMsg` but
      the server never times anyone out.
- [ ] **Structured logging / metrics**. Today `logging.basicConfig` only.
- [ ] **Graceful shutdown** on SIGTERM (close all WS connections, abort engine
      threads, drain outboxes).

## client_flutter/

I couldn't run a Flutter SDK in the dev environment — every code path here is
"should work" rather than "verified".

- [ ] **Actually build it once.** `flutter pub get && flutter run -d macos`.
      Likely-issue list: `Color.withValues` needs Flutter ≥ 3.27 (older SDKs
      need `.withOpacity`); SVG font fallbacks vary by platform.
- [ ] **Real tile artwork** to replace the 37 placeholder SVGs. The Flutter
      side loads by code (`m5.svg`, `z3.svg`, …); swapping files is enough.
- [ ] **Sound**. Tile click on discard, riichi stick clack, win flourish.
- [ ] **Mobile portrait layout**. Current layout fans 4 sides around the
      centre; works on landscape/desktop. Phone portrait needs reshuffling
      (probably 1×3 opponent strip on top, hand+discards stacked below).
- [ ] **Across-screen tile flight on calls**. Current meld animation is local
      (scale-in). Would be nicer to fly the called tile from the discarder's
      pile to the caller's melds. Needs GlobalKey + RenderBox math + a Stack
      overlay.
- [ ] **Furiten warning UI**. After backend supports furiten, show the player
      a subtle "ron blocked" hint.
- [ ] **Replay viewer**. Step through past hands with a scrub bar.
- [ ] **Game settings screen**. Pick ruleset, seed, your seat before connecting.
- [ ] **Accessibility**. No semantics labels on tiles yet.
- [ ] **Connection recovery / auto-reconnect** with backoff.

## AI

- [ ] **Shanten calculator**. The "distance to tenpai" function — building
      block for any non-trivial mahjong AI.
- [ ] **Greedy AI** that minimises shanten + heuristic safe-tile discards.
- [ ] **MCTS / neural baseline**. Standard mahjong-AI direction.
- [ ] **Pluggable AI selection per seat** in `server/session.py` / CLI.

## Tooling

- [ ] **`requirements.txt` / `pyproject.toml`**. Today `websockets` was
      installed manually with `pip install --break-system-packages`. Fix with
      a proper venv + lockfile.
- [ ] **CI**. Run all 53 tests on push; check Flutter analyze + format too.
- [ ] **Linting**: ruff / mypy strict for Python, `flutter analyze` for Dart.
- [ ] **CLAUDE.md** for project conventions if we want Claude Code to follow
      style rules (file layout, naming, no extra comments, …).

## Known soft-failures

- **Random AI doesn't win often** in RiichiRuleset (yaku required); ~20 % of
  seeds end in a win for the AI, the rest are drawn games. With a smarter AI
  hands resolve faster and animations get exercised more.
- **`test_ws_e2e`** has a 60 s per-game timeout. On a slow CI box it could
  flake; raise the timeout or add a faster auto-pick test client.
- **CJK rendering in SVG** depends on system fonts. Designed for `Songti SC` /
  `Noto Serif CJK SC` / `Source Han Serif SC`; if a target device lacks all of
  these, characters fall back to whatever the OS picks.
