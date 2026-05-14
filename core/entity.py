from __future__ import annotations
import itertools


class Entity:
    """Anything addressable by id: a card, a token, a counter, a creature.

    Subclasses (e.g. Tile) carry the domain-specific attributes.
    """
    _id_gen = itertools.count(1)

    def __init__(self) -> None:
        self.id: int = next(Entity._id_gen)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} #{self.id}>"

    def __hash__(self) -> int:
        return self.id

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Entity) and self.id == other.id
