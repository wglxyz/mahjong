"""The Ruleset contract.

AbstractMahjongGame owns the phase machine and all state mutation. The Ruleset answers
the questions that vary between mahjong dialects:

  - What tiles are in the wall?
  - How many tiles per hand, how big is the dead wall?
  - Given a state, what actions are legal for the drawer / for opponents responding to a discard?
  - If multiple opponents claim the same discard, who wins?
  - Is this set of tiles a winning hand under this dialect's yaku rules?
  - How many points does a win pay out?

This split keeps the abstract game ~free of dialect logic. Adding a new region's mahjong
should mean writing one Ruleset and nothing else.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable

from core.action import Action
from core.player import PlayerId
from core.state import GameState
from mahjong.meld import Meld
from mahjong.tile import Tile


@runtime_checkable
class Ruleset(Protocol):
    # ---- constants ---------------------------------------------------------
    seats: int
    initial_hand_size: int
    dead_wall_size: int           # tiles reserved (rinshan + dora indicators); 0 for many cn rulesets

    # ---- wall construction -------------------------------------------------
    def build_wall_tiles(self) -> list[Tile]: ...

    def initial_dealer(self) -> PlayerId: ...

    # ---- decision points ---------------------------------------------------
    def legal_after_draw(
        self, state: GameState, seat: PlayerId, drawn_tile_id: int
    ) -> list[Action]:
        """Drawer just took a tile (live wall or rinshan). What can they do?

        Typically returns a DiscardAction for every tile in hand, plus optionally
        DeclareWin(tsumo) / KanAction(ankan|shouminkan) / DeclareRiichi.
        """

    def legal_after_call(
        self, state: GameState, seat: PlayerId
    ) -> list[Action]:
        """Caller has just melded an opponent's discard and now must discard.

        Most rulesets disallow tsumo here (no draw happened). Some allow shouminkan upgrades
        and additional kans on the same call. v1: usually just Discard*.
        """

    def legal_responses(
        self, state: GameState, discard_seat: PlayerId, discarded_tile_id: int
    ) -> dict[PlayerId, list[Action]]:
        """Per opponent seat: what response actions are legal.

        Every responding seat must get at least a PassAction so the engine has something
        to collect. Ron / Pon / Kan / Chi appear as legal where the ruleset allows.
        """

    def resolve_response_priority(
        self, state: GameState, decisions: dict[PlayerId, Action]
    ) -> tuple[PlayerId, Action] | None:
        """Pick the single winning call among collected responses, or None if all passed.

        Standard priority: Ron > Pon/Kan > Chi. Ties between rons handled per dialect
        (head bump in HK; double ron in riichi).
        """

    # ---- win detection & scoring ------------------------------------------
    def is_winning_hand(
        self,
        hand_tiles: list[Tile],
        melds: list[Meld],
        winning_tile: Tile,
        context: dict,
    ) -> bool: ...

    def score_win(
        self,
        state: GameState,
        winner_seat: PlayerId,
        loser_seat: PlayerId | None,
        winning_tile: Tile,
    ) -> dict[PlayerId, int]:
        """Per-seat point delta (positive = receive, negative = pay)."""

    # ---- side-effect hooks (called by AbstractMahjongGame) ----------------
    def apply_riichi(self, state: GameState, seat: PlayerId) -> None:
        """Side effects of a riichi declaration (sticks, flags). Called *before* the
        accompanying discard, so the ruleset can also tag the discard pile if needed.
        SimpleRuleset and similar dialects without riichi can no-op."""

    def observe(self, state: GameState, event) -> None:
        """Called by AbstractMahjongGame for every event it emits, in order. Lets the
        ruleset maintain inter-action state (ippatsu eligibility, dora reveals on kan,
        etc.) without subscribing to the user-facing EventBus."""
