from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum

from core.entity import Entity


class Visibility(Enum):
    PUBLIC = "public"           # everyone sees contents
    OWNER_ONLY = "owner_only"   # only owner sees contents (others see count)
    HIDDEN = "hidden"           # nobody sees contents (e.g. wall, deck)


class Ordering(Enum):
    ORDERED = "ordered"         # insertion order matters (deck, discard pile)
    UNORDERED = "unordered"     # set-like (hand sorted on display, but order irrelevant)


@dataclass
class Zone:
    name: str
    visibility: Visibility
    ordering: Ordering = Ordering.ORDERED
    owner: int | None = None    # PlayerId, or None for shared zones
    items: list[Entity] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[Entity]:
        return iter(self.items)

    def push(self, entity: Entity) -> None:
        self.items.append(entity)

    def pop(self, index: int = -1) -> Entity:
        return self.items.pop(index)

    def remove(self, entity: Entity) -> None:
        self.items.remove(entity)

    def peek(self, index: int = -1) -> Entity:
        return self.items[index]

    def is_empty(self) -> bool:
        return not self.items
