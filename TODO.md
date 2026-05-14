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
- [ ] **Per-seat state views**. `core` exposes the full state; per-seat
      filtering only happens in `server/serialize.py`. If an in-process
      `ActionProvider` peeked at state, it'd see hidden info. Not a problem for
      Avid's AIs (they cheat anyway), but worth flagging.

## L2 — mahjong abstract game

- [ ] **Per-tile riichi flag in protocol**. The riichi discard should render
      sideways in the discard pile. The event already has `riichi: bool` but
      `TileView` doesn't carry it; a `was_riichi_discard` bit would close the
      gap so clients can visually rotate that tile.
- [ ] **Honba bonus payouts** (本場費). Each honba adds 300 to a win payout
      (split 100 / 100 / 100 for tsumo; 300 from discarder for ron). The honba
      counter is tracked but the bonus isn't applied to scores yet — would
      land in `score_win` / `_do_win`.

## L3 — riichi ruleset

Most of the original simplifications are now implemented (see "Done" section
below). What's left:

- [ ] **Temporary furiten**. Right now we only model *permanent* furiten (own
      discards contain a waiting tile). Standard riichi also has temporary
      furiten — pass up a ron chance and you can't ron again until your next
      own draw.
- [ ] **Tenpai / noten penalty** at drawn game. Standard rule: at exhaustive
      drawn game, tenpai seats split 3000 from non-tenpai seats. `score_draw`
      and `seats_in_tenpai` are both wired — just needs the payout math.
- [ ] **Kazoe yakuman vs counted yakuman option**. We treat 13+ han from
      regular yaku as a single yakuman base (8000); some rules want it just
      capped at sanbaiman.

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
- [ ] **Wire new actions / events to protocol**. `DeclareAbortAction` and the
      `mj_abort_reason` / `mj_winners` / `mj_winner_details` state fields are
      not yet serialised to the client. The Flutter side won't see triple-ron,
      chankan, or nine-terminals correctly until these are mapped in
      `server/serialize.py` and `server/session.py`.

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
- [ ] **Furiten warning UI**. Backend already blocks ron; surface this to the
      player as "ron blocked — you've discarded a winning tile".
- [ ] **Multi-winner (double-ron) result screen**. Win overlay currently
      assumes a single winner — needs to render both panels stacked.
- [ ] **Chankan / nine-terminals UI flow**. Need explicit buttons for
      `DeclareAbortAction` and a chankan response-window indicator.
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
- [ ] **CI**. Run all 102 tests on push; check Flutter analyze + format too.
- [ ] **Linting**: ruff / mypy strict for Python, `flutter analyze` for Dart.
- [ ] **CLAUDE.md** for project conventions if we want Claude Code to follow
      style rules (file layout, naming, no extra comments, …).

---

## Done (this session)

Implemented and tested in `tests/test_riichi_features.py` (37 tests):

- **Furiten** — permanent only; blocks ron when own discards contain a wait.
- **Double riichi** — auto-detected when riichi declared on first turn with no calls.
- **Tenhou** / **Chiihou** — first-turn tsumo, dealer or non-dealer.
- **Kokushi 13-wait** double yakuman; **Chuuren 9-wait** (pure) double yakuman.
- **Kan dora reveals** — extra indicator turned on every kan declaration.
- **Ura dora** — peeked from dead wall only for riichi winners.
- **Nagashi mangan** — drawn-game payout if all your discards are terminal/honor
  and none were called.
- **Comprehensive call coverage** — chi only from upper seat, three positions;
  pon from any opponent; minkan / ankan / shouminkan; riichi'd players can't call.
- **Double ron** — multiple winners share the discarder's payouts.
- **Triple ron abort** — auto-drawn game when 3 simultaneous rons.
- **Head-bump ordering** on double-ron (closer seat scored first).
- **Chankan response window** — opponents may ron on a shouminkan upgrade; new
  `PHASE_CHANKAN`; `is_chankan` yaku triggers on ron.
- **Nine-terminals abort** — player-initiated `DeclareAbortAction`, offered on
  first turn when 9+ unique terminal/honor codes in hand.
- **Four-winds first-round abort** — auto-drawn when all 4 first discards
  match the same wind.
- **Four-riichi abort** — auto-drawn when all 4 players riichi'd.
- **Four-kans abort** — auto-drawn when ≥4 kans across ≥2 different players
  (single-player 4 kans remains suukantsu yakuman).
- **Multi-hand match** — `AbstractMahjongGame` plays full East-only (1 round =
  4 hands) or half-east (2 rounds = 8 hands) with dealer rotation, renchan on
  dealer-win, drawn-tenpai-renchan (via `seats_in_tenpai` hook), riichi-stick
  pool carryover, per-hand result snapshots stored in `mj_hand_results`.
- **Match shape config** — `rounds_per_match`, `initial_points` (default 25000),
  `tenpai_renchan` are constructor knobs on `AbstractMahjongGame`.

## Known soft-failures

- **Random AI doesn't win often** in RiichiRuleset (yaku required); roughly
  one in five seeds ends in a win for the AI, the rest are drawn games. With a
  smarter AI hands resolve faster and animations get exercised more.
- **`test_ws_e2e`** has a 60 s per-game timeout. On a slow CI box it could
  flake; raise the timeout or add a faster auto-pick test client.
- **CJK rendering in SVG** depends on system fonts. Designed for `Songti SC` /
  `Noto Serif CJK SC` / `Source Han Serif SC`; if a target device lacks all of
  these, characters fall back to whatever the OS picks.
