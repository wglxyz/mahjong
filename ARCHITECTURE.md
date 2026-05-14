# Architecture

A mahjong game built as a strict-layered system: a generic board-game engine on
the bottom, mahjong primitives on top of that, regional rule variants on top of
that, and UI / AI as orthogonal plugins. The Python engine is authoritative;
the Flutter client is a thin renderer that asks the server "what are my legal
moves?" and sends back which one it picked.

## Layer map

```
┌─────────────────────────────────────────────────────────────────┐
│ client_flutter/   Flutter UI — Mac / iOS / Android (one codebase) │
└─────────────────────────────────────────────────────────────────┘
                              │ WebSocket + JSON
┌─────────────────────────────────────────────────────────────────┐
│ server/           WS server + per-seat snapshot + ActionProvider │
│                   adapter that bridges asyncio ↔ engine thread   │
└─────────────────────────────────────────────────────────────────┘
                              │ ActionProvider protocol
┌─────────────────────────────────────────────────────────────────┐
│ L3  rules/        SimpleRuleset, RiichiRuleset (dialects)        │
├─────────────────────────────────────────────────────────────────┤
│ L2  mahjong/      Tile, Meld, Action types, AbstractMahjongGame  │
│                   (phase machine, no dialect knowledge)          │
├─────────────────────────────────────────────────────────────────┤
│ L1  core/         Entity, Zone, Resource, Engine, GameDef        │
│                   (generic, validated by `games/topcard/` toy)    │
└─────────────────────────────────────────────────────────────────┘
```

**Invariant:** each layer talks only to the layer directly below it. Adding a
new dialect requires writing one Ruleset class — engine and abstract-game code
stay untouched. Adding a new UI requires implementing `ActionProvider` (or for
remote clients, speaking the WS protocol). These invariants are load-bearing.

## L1 — core/

Generic turn-based-game engine. Knows about entities and zones and turns; knows
nothing about mahjong, cards, or rules.

| File | Role |
|---|---|
| `entity.py` | `Entity` — anything addressable by id |
| `zone.py` | `Zone` — container of entities with `Visibility (public / owner_only / hidden)` and `Ordering (ordered / unordered)` |
| `resource.py` | Named numeric value with optional bounds (points, plays, …) |
| `player.py` | id + name + dict of zones + dict of resources |
| `state.py` | `GameState`: players + shared zones + RNG + phase |
| `action.py` / `event.py` | Frozen records that flow through the engine |
| `event_bus.py` | Pub/sub |
| `rng.py` | Seedable random source (wraps stdlib `Random`) |
| `game_def.py` | `GameDef` Protocol (`setup`, `decision_point`, `apply`, `is_terminal`, `winners`) + `DecisionPoint` (supports **multiple acting seats** simultaneously — the mechanism behind mahjong's chi/pon/kan/ron response window) |
| `action_provider.py` | `ActionProvider` Protocol: `choose(state, me, legal) -> Action`. UIs and AIs both implement this. |
| `engine.py` | Main loop: `setup → broadcast setup events → while not terminal: decision_point → ask each provider → apply → broadcast events` |

Validated by `games/topcard/` — a non-mahjong toy game (N players draw from a
hidden deck to score piles). Demonstrates the L1 abstractions are sufficient.

## L2 — mahjong/

Mahjong-specific primitives + the dialect-agnostic phase machine.

| File | Role |
|---|---|
| `tile.py` | `Tile(Entity)` — suit (`m`/`p`/`s`/`z`/`f`) + rank + red flag |
| `meld.py` | `Meld(Entity)` — holds a tuple of tiles, knows type and caller direction |
| `actions.py` | Standard mahjong action types: `Discard`, `Pass`, `Chi`, `Pon`, `Kan`, `DeclareWin`, `DeclareRiichi` |
| `events.py` | `HandStarted`, `TileDrawn`, `TileDiscarded`, `MeldFormed`, `RiichiDeclared`, `HandWon`, `HandDrawn` |
| `ruleset.py` | `Ruleset` Protocol — what every dialect must implement |
| `abstract_game.py` | `AbstractMahjongGame(GameDef)`: owns the phase machine, delegates every dialect-specific question (legal actions, win shape, scoring) to the Ruleset |

### Phase machine

```
setup ──► AFTER_DRAW (dealer's opening draw already done)

AFTER_DRAW ── Discard ──► RESPONSE
            ── DeclareWin(tsumo) ──► END
            ── KanAction(ankan|shouminkan) ──► AFTER_DRAW (rinshan draw)
            ── DeclareRiichi(+discard) ──► RESPONSE

RESPONSE   ── (all Pass) ──► AFTER_DRAW for next seat (auto-draw); END if wall empty
            ── DeclareWin(ron) ──► END
            ── Chi/Pon ──► AFTER_CALL for caller
            ── Kan(minkan) ──► AFTER_DRAW for caller (rinshan draw)

AFTER_CALL ── Discard ──► RESPONSE
```

The abstract game manipulates zones (tiles between hand/discards/melds), records
state via well-known keys in `state.attrs`, and emits events. It does **not**
look at tile content beyond moving entities around — that's the Ruleset's job.

### Ruleset hooks

Each Ruleset provides:

- **Constants**: `seats`, `initial_hand_size`, `dead_wall_size`
- **Wall**: `build_wall_tiles()`, `initial_dealer()`
- **Legal actions**: `legal_after_draw`, `legal_after_call`, `legal_responses`
- **Resolution**: `resolve_response_priority(decisions)` — ron beats pon/kan beats chi
- **Win check**: `is_winning_hand(tiles, melds, winning_tile, ctx)`
- **Scoring**: `score_win(state, winner, loser, winning_tile) -> {seat: delta}`
- **Side effects**: `apply_riichi(state, seat)` for declaration bookkeeping, `observe(state, event)` for streaming state updates (ippatsu flags, dora reveals, …)

## L3 — rules/

### `rules/simple.py`

A minimal dialect to prove the contract. 3 suits × 9 × 4 = 108 tiles. No honors,
no flowers, no chi, no kan, no riichi, no yaku requirement. Win = 4 melds + 1
pair, scored as `winner +3 / others -1` (zero-sum).

### `rules/riichi/`

Japanese standard riichi with ~30 yaku and proper fu/han scoring.

| File | Role |
|---|---|
| `tileset.py` | 136-tile wall builder + optional red 5s + indicator → dora resolution |
| `decompose.py` | Enumerates all valid winning hand cuts: standard (4 melds + 1 pair), chiitoitsu (7 pairs), kokushi (13 orphans) |
| `yaku.py` | 19 regular yaku + 12 yakuman. Aggregator picks the highest-han decomposition; dora/red dora/ura dora as add-on han. |
| `score.py` | Fu calc (base 20 + tsumo/ron/concealed/melds/pair/wait) + han→base via `fu × 2^(han+2)` with mangan/haneman/baiman/sanbaiman/yakuman caps. Per-seat payouts include dealer 1.5× and round to 100. |
| `ruleset.py` | The `Ruleset` implementation. Wires the four files above into the abstract game. Maintains riichi/ippatsu/rinshan via `observe()`. |

Known riichi simplifications are listed in `TODO.md`.

## server/

Bridges the Python engine to remote clients over WebSocket. The engine is
synchronous; `websockets` runs on asyncio. The bridge:

```
asyncio task               engine thread
   │                            │
   │ ws.send(decision)          │ provider.choose() ← blocks on Event
   │ ws.recv() → deliver(...)   │                  ← wakes up, returns Action
   │                            │ engine.apply()
   │ ← outbox queue ← engine emits events
```

| File | Role |
|---|---|
| `protocol.py` | All wire message types as dataclasses with `to_dict`/`from_dict` |
| `serialize.py` | `GameState` → `Snapshot` from a specific seat's view (own hand visible, opponent hands counted) |
| `ws_provider.py` | `WebSocketProvider(ActionProvider)`: thread-safe queue + `Event` bridge |
| `session.py` | One session = 1 WS client + 3 AIs + 1 Engine in a background thread |
| `server.py` | `:8765` WS endpoint. Each connection ⇒ one fresh `Session`. |

## client_flutter/

Native client (Mac / iOS / Android, single codebase). Pure renderer + button
dispatcher: no game logic. 17 Dart files + 38 placeholder SVG tiles.

| Layer | Files |
|---|---|
| Entry | `main.dart`, `theme.dart` |
| Wire | `protocol/messages.dart`, `services/ws_client.dart` |
| State | `state/game_state.dart` (`ChangeNotifier`) |
| Screens | `screens/connect_screen.dart`, `screens/game_screen.dart` |
| Widgets | `tile.dart`, `animated_tile.dart`, `hand_view.dart`, `discard_grid.dart`, `meld_view.dart`, `seat_panel.dart`, `riichi_stick.dart`, `table_view.dart`, `action_bar.dart`, `win_overlay.dart` |
| Assets | 37 tile SVGs + back, all generated by `scripts/gen_tiles.py` |

### Animations

Component-local (no global overlay). New entries are keyed by entity id so
Flutter reuses State for tiles that stayed in place; new tiles get fresh State
and animate. Coverage:

- **Discard**: slide-in from above, fade (240 ms easeOut)
- **Meld**: scale-bounce in from the bottom (380 ms easeOutBack)
- **Drawn tile**: elastic bounce (380 ms `elasticOut`)
- **Score change**: numeric tween (600 ms easeOutCubic)
- **Active seat**: gold breathing glow via `sin(πt)` strength
- **Riichi stick**: slide-up from below (520 ms easeOutBack)
- **Win overlay**: scale-in + rotating gold halo + yaku rows staggered slide-fade + score ticker

## Protocol (WebSocket + JSON)

The full message catalogue. Server → Client are tagged with `type`:

```
welcome      { your_seat, seats[], ruleset }
snapshot     { your_seat, round_wind, hand_number, dealer, wall_count,
               dora_indicators[], seats[ {seat, name, points, riichi,
               melds[], discards[], hand[]?, hand_count} ],
               current_seat, phase, last_drawn_tile? }
event        { event: { kind: "tile_drawn"|"tile_discarded"|"meld_formed"|... } }
decision     { actions: [ {id, kind, tiles[]?, extra{}?} ], deadline_ms? }
hand_ended   { result: "win"|"drawn", winner?, loser?, score, han?, fu?, yaku[] }
error        { error }

C → S:
decide       { action_id }
request_snapshot
```

**Action ids** are opaque strings (e.g. `"a3"`). Server keeps a map back to real
`Action` objects; client just shows them and echos the id. **Hand visibility**:
the per-seat filtering happens in `serialize.py:make_snapshot()` — opponent
hands appear as `hand_count` only, no `hand` field.

## Composition entry points

| Command | What it does |
|---|---|
| `python -m games.topcard.play` | L1 sanity check (toy non-mahjong game) |
| `python -m games.mahjong.play` | 4 AIs, SimpleRuleset |
| `python -m games.mahjong.play_cli` | 1 human (terminal) + 3 AIs, SimpleRuleset |
| `python -m games.mahjong.play_riichi --seed N` | 4 AIs, RiichiRuleset |
| `python -m server.server --ruleset riichi --port 8765` | WS server for Flutter client |

## Tests (53 across 8 files)

| Suite | Coverage |
|---|---|
| `test_topcard` | Toy game terminates, deterministic |
| `test_simple_ruleset` | Win-shape detection edge cases (chiitoitsu, mixed melds, …) |
| `test_mahjong_engine` | AbstractMahjongGame + Simple across 40 seeds, zero-sum, deterministic |
| `test_riichi_decompose` | Standard / chiitoitsu / kokushi decompositions, multi-decomp hands |
| `test_riichi_yaku` | Each major yaku, double-wind, ron-breaks-suuankou |
| `test_riichi_score` | Fu rounding, mangan/yakuman cap, dealer vs non-dealer payouts, zero-sum |
| `test_riichi_engine` | Riichi engine 10+ seeds, zero-sum, win-has-yaku |
| `test_ws_e2e` | Start server + Python WS client + auto-decide → full hand for both rulesets |

## Extending the system

**Adding a new dialect** (e.g. Hong Kong, Sichuan, CN standard):
1. `mkdir rules/<dialect>/` and write `ruleset.py` implementing the `Ruleset` Protocol.
2. Reuse `rules/riichi/decompose.py` (or write your own variant).
3. Wire into `server/session.py` (a 2-line `if` branch).

**Adding a new UI** (web, TUI, native):
1. Implement `ActionProvider` directly if in-process; or
2. Speak the WS JSON protocol described above — server doesn't care which language the client is in.

**Adding a new AI**:
1. Implement `ActionProvider.choose(state, me, legal) -> Action`.
2. Plug into the providers dict in `server/session.py` or any `games/*/play_*.py`.

The architecture's main bet — "new variants and new UIs don't touch the engine"
— has been validated twice: adding RiichiRuleset (large) and adding the
Flutter+WS UI (large) both required zero changes to `core/`, and only one
trivial cross-cutting change to `mahjong/` (the `apply_riichi` / `observe`
ruleset hooks).
