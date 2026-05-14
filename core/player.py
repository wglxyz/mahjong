from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.zone import Zone
    from core.resource import Resource

PlayerId = int


@dataclass
class Player:
    """A participant in the game. Owns named zones and resources, plus a bag of attrs."""
    id: PlayerId
    name: str
    zones: dict[str, "Zone"] = field(default_factory=dict)
    resources: dict[str, "Resource"] = field(default_factory=dict)
    attrs: dict[str, object] = field(default_factory=dict)

    def zone(self, name: str) -> "Zone":
        return self.zones[name]

    def resource(self, name: str) -> "Resource":
        return self.resources[name]
