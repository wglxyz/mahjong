# Avid

A mahjong game engine in Python, designed for swappable rule variants and
swappable UIs. Plays Japanese riichi with full(ish) yaku + scoring; also plays
a simplified dialect. Comes with a CLI and a Flutter native client (Mac / iOS /
Android, one codebase) talking to the engine over WebSocket.

```
core/  ─── L1  generic turn-based-game engine (works for non-mahjong too)
mahjong/ ─ L2  mahjong primitives + dialect-agnostic phase machine
rules/ ─── L3  SimpleRuleset, RiichiRuleset (each ~one file to add a region)
server/ ── WebSocket bridge
client_flutter/ Flutter UI
games/ ─── composition / demos (incl. a non-mahjong toy game)
tests/ ─── 53 tests across 8 suites
```

## Quickstart

```bash
# play a hand with 4 random AIs, all in the terminal
python -m games.mahjong.play_riichi --seed 7

# play as a human against 3 AIs in the terminal (SimpleRuleset)
python -m games.mahjong.play_cli

# run the WebSocket server, then start the Flutter client
python -m server.server --ruleset riichi --port 8765
cd client_flutter && flutter pub get && flutter run -d macos

# run the test suite
for t in test_topcard test_simple_ruleset test_mahjong_engine \
         test_riichi_decompose test_riichi_yaku test_riichi_score \
         test_riichi_engine test_ws_e2e; do
    python -u -m tests.$t
done
```

## Docs

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — full layered design, module map, WS
  protocol, extension points
- **[TODO.md](TODO.md)** — known simplifications and next-step features by layer
- **[client_flutter/README.md](client_flutter/README.md)** — Flutter setup,
  asset-replacement workflow

## Design principles

1. **Strict layering.** New mahjong dialect = new file in `rules/`; engine and
   abstract game don't change.
2. **Backend is authoritative.** Client never validates rules — server hands
   it a list of legal action ids; client picks one and echoes back.
3. **Same `ActionProvider` interface for UIs and AIs.** Engine doesn't
   distinguish.
4. **Tests are the contract.** Layer separation is enforced by tests that the
   abstract game runs against both rulesets unchanged.
