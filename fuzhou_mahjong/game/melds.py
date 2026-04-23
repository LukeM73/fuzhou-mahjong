"""
Melds (chow / pung / kong) and call detection.

Fuzhou-specific rules embedded here:
  * Only numbered tiles form melds.  Honours are bonus tiles.
  * The Gold (Jin) wildcard substitutes for any tile in a chow or pung.
  * A discarded Gold tile cannot be claimed by anyone.
  * Chow may only be called by the player immediately downstream of the
    discarder (the "next" player in turn-order).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from .tiles import Suit, Tile, count_tile


class MeldType(Enum):
    CHOW = "chow"          # 1-2-3 same suit
    PUNG = "pung"          # 5-5-5
    KONG_EXPOSED = "kong_exposed"
    KONG_CONCEALED = "kong_concealed"
    KONG_PROMOTED = "kong_promoted"   # added 4th to an existing exposed pung

    @property
    def is_kong(self) -> bool:
        return self in (
            MeldType.KONG_EXPOSED,
            MeldType.KONG_CONCEALED,
            MeldType.KONG_PROMOTED,
        )


@dataclass
class Meld:
    type: MeldType
    tiles: List[Tile]                     # the actual tiles forming it (incl. golds used)
    called_from_seat: Optional[int] = None  # who discarded it (None for concealed/self-draw kong)
    claimed_tile: Optional[Tile] = None     # the discard that triggered this call

    @property
    def is_kong(self) -> bool:
        return self.type.is_kong

    @property
    def is_concealed(self) -> bool:
        return self.type == MeldType.KONG_CONCEALED

    def __repr__(self) -> str:
        body = "".join(t.short for t in self.tiles)
        return f"<{self.type.value}:{body}>"


# ------------------------------------------------------------------ predicates


def _is_chow(a: Tile, b: Tile, c: Tile) -> bool:
    if not (a.is_numbered and b.is_numbered and c.is_numbered):
        return False
    if a.suit != b.suit or b.suit != c.suit:
        return False
    vs = sorted([a.value, b.value, c.value])
    return vs[0] + 1 == vs[1] and vs[1] + 1 == vs[2]


def _is_pung(a: Tile, b: Tile, c: Tile) -> bool:
    return a == b == c and a.is_numbered


# ------------------------------------------------------------------ call detection


@dataclass
class Call:
    """A meld a player is allowed to call on the current discard."""
    type: MeldType
    tiles_from_hand: List[Tile]   # tiles the caller commits from their hand
    discard: Tile                  # the tile being claimed

    def all_tiles(self) -> List[Tile]:
        return [*self.tiles_from_hand, self.discard]


def find_calls(
    hand_tiles: List[Tile],
    discard: Tile,
    is_next_player: bool,
    gold: Optional[Tile],
) -> List[Call]:
    """
    Enumerate every legal chow/pung/kong this player could call on `discard`.

    The discard itself is *not* in `hand_tiles`.  Gold tiles cannot be claimed
    (per Fuzhou rules) so the discard must not be the gold.
    """
    if not discard.is_numbered:
        return []
    if gold is not None and discard == gold:
        return []   # discarded gold cannot be called

    calls: List[Call] = []

    # ----- pung -----
    n_match = count_tile(hand_tiles, discard)
    if n_match >= 2:
        calls.append(Call(MeldType.PUNG, [discard, discard], discard))
    if n_match >= 3:
        calls.append(Call(MeldType.KONG_EXPOSED, [discard, discard, discard], discard))

    # ----- chow (only the next player) -----
    if is_next_player:
        v, suit = discard.value, discard.suit
        for offsets in ((-2, -1), (-1, 1), (1, 2)):
            need = [Tile(suit, v + o) for o in offsets]
            if all(1 <= t.value <= 9 for t in need) and all(t in hand_tiles for t in need):
                # avoid duplicate chows like 1-2-3 vs 2-3-4 with same hand tiles
                calls.append(Call(MeldType.CHOW, list(need), discard))

    return calls


# ------------------------------------------------------------------ kong helpers


def find_concealed_kongs(hand_tiles: List[Tile]) -> List[Tile]:
    """Return the tile-values for which the player holds 4 concealed copies."""
    seen = set()
    out: List[Tile] = []
    for t in hand_tiles:
        if t in seen:
            continue
        if count_tile(hand_tiles, t) == 4 and t.is_numbered:
            out.append(t)
        seen.add(t)
    return out


def find_promotable_kongs(hand_tiles: List[Tile], melds: List[Meld]) -> List[Tile]:
    """A previously-exposed pung can be upgraded to a kong by adding the 4th tile."""
    out: List[Tile] = []
    for m in melds:
        if m.type == MeldType.PUNG and m.tiles[0] in hand_tiles:
            out.append(m.tiles[0])
    return out
