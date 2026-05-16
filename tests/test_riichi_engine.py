"""Integration smoke test: RiichiRuleset + AbstractMahjongGame doesn't crash and
produces zero-sum, deterministic results."""
from __future__ import annotations

from core.engine import Engine
from core.event_bus import EventBus
from core.rng import RNG
from core.state import GameState
from games.mahjong.play_riichi import WinSeekingAI
from mahjong.abstract_game import K_RESULT, AbstractMahjongGame
from rules.riichi.ruleset import RiichiRuleset


def _run_one(seed: int) -> dict:
    game = AbstractMahjongGame(RiichiRuleset(), player_names=["E", "S", "W", "N"])
    state = GameState(rng=RNG(seed=seed))
    providers = {i: WinSeekingAI(seed=seed * 7 + i) for i in range(4)}
    engine = Engine(game, state, providers, EventBus(), max_steps=50_000)
    engine.run()
    return {
        "result": state.attrs.get(K_RESULT),
        "points": {i: state.players[i].resources["points"].value for i in range(4)},
        "yaku": state.attrs.get("mj_last_yaku"),
        "han": state.attrs.get("mj_last_han"),
    }


def test_terminates_no_crash_across_seeds() -> None:
    for seed in range(10):
        r = _run_one(seed)
        assert r["result"] in ("win", "drawn"), f"seed {seed}: bad result {r['result']}"


def test_points_conservation() -> None:
    """initial_points 25000 × 4 = 100000. Sticks in pool (if a hand ended drawn last)
    may eat into this; allow the difference to be a small multiple of 1000."""
    expected = 25000 * 4
    for seed in range(10):
        r = _run_one(seed)
        total = sum(r["points"].values())
        diff = expected - total
        assert diff % 1000 == 0 and 0 <= diff <= 10000, (
            f"seed {seed}: lost {diff} points beyond stick pool: {r['points']}"
        )


def test_win_has_yaku() -> None:
    saw = False
    for seed in range(20):
        r = _run_one(seed)
        if r["result"] == "win":
            saw = True
            assert r["yaku"], f"seed {seed}: winner had no yaku list"
            assert r["han"] >= 1, f"seed {seed}: han < 1 ({r['han']})"
    assert saw, "expected at least one win in 20 seeds"


def test_determinism() -> None:
    a = _run_one(seed=11)
    b = _run_one(seed=11)
    assert a == b


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items() if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f()
        print(f"  ✓ {n}")
    print(f"\n{len(fns)} tests passed")
