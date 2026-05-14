"""Multi-hand match tests: renchan, rotation, round-wind advance, match termination,
and riichi-stick-pool carryover."""
from __future__ import annotations

from core.engine import Engine
from core.event_bus import EventBus
from core.rng import RNG
from core.state import GameState
from mahjong.abstract_game import (
    AbstractMahjongGame,
    K_DEALER_SEAT,
    K_HAND_NUMBER,
    K_HAND_RESULTS,
    K_HONBA,
    K_LAST_DISCARD_SEAT,
    K_PHASE,
    K_RESULT,
    K_RIICHI_STICKS_POOL,
    K_ROUND_WIND,
    K_WINNER,
    PHASE_END,
    PHASE_HAND_END,
)
from rules.riichi.ruleset import RiichiRuleset


def _new_game(rounds_per_match: int = 2, **kwargs) -> tuple[AbstractMahjongGame, GameState]:
    game = AbstractMahjongGame(
        RiichiRuleset(),
        player_names=["E", "S", "W", "N"],
        rounds_per_match=rounds_per_match,
        **kwargs,
    )
    state = GameState(rng=RNG(seed=0))
    game.setup(state)
    return game, state


# ──────────────────────────────────────────────────────────────────────────
# transition primitives
# ──────────────────────────────────────────────────────────────────────────
def test_renchan_on_dealer_win() -> None:
    game, state = _new_game(rounds_per_match=1)
    dealer_before = state.attrs[K_DEALER_SEAT]
    hand_before = state.attrs[K_HAND_NUMBER]
    state.attrs[K_PHASE] = PHASE_HAND_END
    state.attrs[K_RESULT] = "win"
    state.attrs["mj_winners"] = [dealer_before]
    state.attrs[K_WINNER] = dealer_before

    game._advance_hand_or_end_match(state)
    assert state.attrs[K_DEALER_SEAT] == dealer_before, "dealer should stay"
    assert state.attrs[K_HAND_NUMBER] == hand_before, "hand number stays"
    assert state.attrs[K_HONBA] == 1


def test_rotation_on_non_dealer_win() -> None:
    game, state = _new_game(rounds_per_match=1)
    dealer_before = state.attrs[K_DEALER_SEAT]
    state.attrs[K_PHASE] = PHASE_HAND_END
    state.attrs[K_RESULT] = "win"
    non_dealer = (dealer_before + 1) % 4
    state.attrs["mj_winners"] = [non_dealer]
    state.attrs[K_WINNER] = non_dealer

    game._advance_hand_or_end_match(state)
    assert state.attrs[K_DEALER_SEAT] == (dealer_before + 1) % 4
    assert state.attrs[K_HAND_NUMBER] == 2
    assert state.attrs[K_HONBA] == 0


def test_drawn_dealer_tenpai_renchan() -> None:
    game, state = _new_game(rounds_per_match=1, tenpai_renchan=True)
    dealer = state.attrs[K_DEALER_SEAT]
    # mark drawn-with-dealer-tenpai by manually adjusting hand to tenpai shape
    # easiest: empty all hands except dealer's tenpai hand
    from mahjong.tile import Tile
    for s, p in state.players.items():
        p.zones["hand"].items.clear()
    state.players[dealer].zones["hand"].items.extend([
        Tile("m", 1), Tile("m", 1), Tile("m", 1),
        Tile("p", 2), Tile("p", 2), Tile("p", 2),
        Tile("s", 3), Tile("s", 3), Tile("s", 3),
        Tile("m", 9), Tile("m", 9), Tile("m", 9),
        Tile("p", 5),
    ])
    state.attrs[K_PHASE] = PHASE_HAND_END
    state.attrs[K_RESULT] = "drawn"
    state.attrs["mj_winners"] = []

    game._advance_hand_or_end_match(state)
    assert state.attrs[K_DEALER_SEAT] == dealer, "tenpai dealer should renchan"
    assert state.attrs[K_HONBA] == 1


def test_drawn_dealer_noten_rotates() -> None:
    game, state = _new_game(rounds_per_match=1, tenpai_renchan=True)
    dealer = state.attrs[K_DEALER_SEAT]
    # dealer hand left empty → noten
    for s, p in state.players.items():
        p.zones["hand"].items.clear()
    state.attrs[K_PHASE] = PHASE_HAND_END
    state.attrs[K_RESULT] = "drawn"
    state.attrs["mj_winners"] = []

    game._advance_hand_or_end_match(state)
    assert state.attrs[K_DEALER_SEAT] == (dealer + 1) % 4
    assert state.attrs[K_HONBA] == 1  # honba bumps on rotation-after-draw too


def test_round_wind_advances_after_full_round() -> None:
    game, state = _new_game(rounds_per_match=2)
    # simulate E4 ending with rotation
    state.attrs[K_DEALER_SEAT] = 3
    state.attrs[K_HAND_NUMBER] = 4
    state.attrs[K_ROUND_WIND] = 1
    state.attrs[K_PHASE] = PHASE_HAND_END
    state.attrs[K_RESULT] = "win"
    state.attrs["mj_winners"] = [0]  # non-dealer
    state.attrs[K_WINNER] = 0

    game._advance_hand_or_end_match(state)
    assert state.attrs[K_ROUND_WIND] == 2, "round wind should advance to South"
    assert state.attrs[K_HAND_NUMBER] == 1
    assert state.attrs[K_DEALER_SEAT] == 0


def test_match_end_after_last_round() -> None:
    game, state = _new_game(rounds_per_match=1)
    state.attrs[K_DEALER_SEAT] = 3
    state.attrs[K_HAND_NUMBER] = 4
    state.attrs[K_ROUND_WIND] = 1
    state.attrs[K_PHASE] = PHASE_HAND_END
    state.attrs[K_RESULT] = "win"
    state.attrs["mj_winners"] = [0]
    state.attrs[K_WINNER] = 0

    game._advance_hand_or_end_match(state)
    assert state.attrs[K_PHASE] == PHASE_END, "match should end after E4 with rotation"


# ──────────────────────────────────────────────────────────────────────────
# riichi stick pool
# ──────────────────────────────────────────────────────────────────────────
def test_riichi_pool_paid_to_closest_winner() -> None:
    game, state = _new_game(rounds_per_match=1)
    dealer = state.attrs[K_DEALER_SEAT]
    state.attrs[K_RIICHI_STICKS_POOL] = 3
    state.attrs[K_PHASE] = PHASE_HAND_END
    state.attrs[K_RESULT] = "win"
    state.attrs["mj_winners"] = [(dealer + 2) % 4]
    state.attrs[K_WINNER] = (dealer + 2) % 4
    state.attrs[K_LAST_DISCARD_SEAT] = dealer
    points_before = state.players[(dealer + 2) % 4].resources["points"].value

    game._advance_hand_or_end_match(state)
    points_after = state.players[(dealer + 2) % 4].resources["points"].value
    assert points_after - points_before == 3000
    assert state.attrs[K_RIICHI_STICKS_POOL] == 0


def test_riichi_pool_persists_through_drawn_hand() -> None:
    game, state = _new_game(rounds_per_match=2)
    state.attrs[K_RIICHI_STICKS_POOL] = 2
    state.attrs[K_PHASE] = PHASE_HAND_END
    state.attrs[K_RESULT] = "drawn"
    state.attrs["mj_winners"] = []

    game._advance_hand_or_end_match(state)
    # pool unchanged
    assert state.attrs[K_RIICHI_STICKS_POOL] == 2


# ──────────────────────────────────────────────────────────────────────────
# end-to-end smoke
# ──────────────────────────────────────────────────────────────────────────
def test_east_only_runs_at_least_4_hands() -> None:
    """Engine plays the full East round; expect 4+ hands (renchans add to count)."""
    from games.mahjong.play_riichi import WinSeekingAI
    game = AbstractMahjongGame(
        RiichiRuleset(), ["E","S","W","N"], rounds_per_match=1,
    )
    state = GameState(rng=RNG(seed=3))
    providers = {i: WinSeekingAI(seed=i) for i in range(4)}
    engine = Engine(game, state, providers, EventBus(), max_steps=100_000)
    engine.run()
    results = state.attrs[K_HAND_RESULTS]
    assert len(results) >= 4, f"east-only round should produce ≥4 hand results, got {len(results)}"
    assert state.attrs[K_PHASE] == PHASE_END


def test_half_east_runs_at_least_8_hands() -> None:
    from games.mahjong.play_riichi import WinSeekingAI
    game = AbstractMahjongGame(
        RiichiRuleset(), ["E","S","W","N"], rounds_per_match=2,
    )
    state = GameState(rng=RNG(seed=5))
    providers = {i: WinSeekingAI(seed=i) for i in range(4)}
    engine = Engine(game, state, providers, EventBus(), max_steps=200_000)
    engine.run()
    results = state.attrs[K_HAND_RESULTS]
    assert len(results) >= 8, f"half-east should produce ≥8 hand results, got {len(results)}"
    assert state.attrs[K_PHASE] == PHASE_END


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    fns = [(n, f) for n, f in vars(mod).items() if n.startswith("test_") and callable(f)]
    for n, f in fns:
        f()
        print(f"  ✓ {n}")
    print(f"\n{len(fns)} tests passed")
