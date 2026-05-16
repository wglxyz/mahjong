from __future__ import annotations

from dataclasses import dataclass

from core.player import PlayerId


@dataclass(frozen=True)
class Action:
    """Base record for a player's intent. Concrete games subclass with extra fields.

    Frozen because actions flow across the engine/UI/AI boundary and should be values.
    """
    actor: PlayerId
