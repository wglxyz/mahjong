from __future__ import annotations
from collections.abc import Callable

from core.event import Event

Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subs: list[Subscriber] = []

    def subscribe(self, fn: Subscriber) -> None:
        self._subs.append(fn)

    def publish(self, event: Event) -> None:
        for fn in self._subs:
            fn(event)
