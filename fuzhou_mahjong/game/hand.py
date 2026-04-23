"""
A player's hand.  Holds concealed tiles, exposed melds, declared concealed
kongs, and the flower rack.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .tiles import Tile, sorted_tiles


@dataclass
class Hand:
    concealed: List[Tile] = field(default_factory=list)   # closed tiles
    melds: List["Meld"] = field(default_factory=list)     # exposed (chow/pung/kong)
    flowers: List[Tile] = field(default_factory=list)     # bonus rack
    last_draw: Optional[Tile] = None                      # for self-draw checks
    just_called: bool = False                             # set after a call

    # ----- queries -----
    @property
    def n_concealed(self) -> int:
        return len(self.concealed)

    @property
    def n_total(self) -> int:
        """Number of tiles 'logically' in hand (incl. exposed)."""
        n = self.n_concealed
        for m in self.melds:
            n += 4 if m.is_kong else 3
        return n

    def sorted(self) -> List[Tile]:
        return sorted_tiles(self.concealed)

    # ----- mutation -----
    def add(self, tile: Tile) -> None:
        self.concealed.append(tile)

    def remove(self, tile: Tile) -> None:
        try:
            self.concealed.remove(tile)
        except ValueError as e:
            raise ValueError(f"Tile {tile} not in hand {self.concealed}") from e

    def remove_many(self, tiles: List[Tile]) -> None:
        for t in tiles:
            self.remove(t)
