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
    ) -> list[tuple[PlayerId, Action]] | None:
        """Resolve the response window. Return value:

          - None: all opponents passed → continue to next draw
          - empty list []: the response triggers an abort (e.g. triple ron in riichi)
          - non-empty list: each tuple is a (seat, action) that "wins" the call. Usually
            one element; double ron yields two elements (both winners get scored).

        Standard priority: Ron > Pon/Kan > Chi.
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

    def score_draw(self, state: GameState) -> dict[PlayerId, int]:
        """Per-seat point deltas at a drawn game. Empty / all-zeros for dialects with
        no special draws. Riichi uses this for nagashi mangan (and could be extended for
        tenpai/noten penalties)."""

    def check_abort_conditions(self, state: GameState) -> str | None:
        """Called after every event apply. Return a short reason tag if the hand should
        immediately abort (drawn), otherwise None.

        Riichi: four-wind first-discards, four-kans, four-riichi, etc.
        SimpleRuleset: never aborts.
        """

    def seats_in_tenpai(self, state: GameState) -> list[PlayerId]:
        """Which seats are currently tenpai (one tile away from a win shape).

        Used by AbstractMahjongGame for the drawn-game renchan check (dealer-tenpai
        keeps the dealer) and may feed tenpai/noten payouts. SimpleRuleset returns
        [] since it has no tenpai concept; RiichiRuleset checks each seat's hand.
        """
