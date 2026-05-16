from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    """Base record for something that already happened. Concrete games subclass.

    Events are broadcast on the EventBus; UI renders them, AI may train on them,
    rules can subscribe for triggered effects.
    """
    pass
