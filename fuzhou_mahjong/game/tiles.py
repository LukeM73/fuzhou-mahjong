"""
Fuzhou Mahjong tile model.

Fuzhou uses the full 144-tile set, but with an unusual twist:
  * The 108 numbered tiles (Characters / Dots / Bamboo, 1-9, x4 each) are the
    only tiles used to form melds.
  * The 28 honor tiles (4 Winds x4, 3 Dragons x4) and 8 Flower/Season tiles
    are "bonus" tiles -- when drawn, they immediately go to a player's flower
    rack and the player draws a replacement.  They contribute fan to scoring
    but are never part of the playing hand.
  * One tile-value is designated the "Gold" (金 Jin) at the start of the round
    via an indicator-tile reveal.  All four copies of that tile-value become
    universal wildcards.

This module is pure-Python and has no UI / network dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class Suit(Enum):
    MAN = "man"          # 萬 / Characters / Cracks
    PIN = "pin"          # 筒 / Dots / Circles
    SOU = "sou"          # 條 / Bamboo / Bams
    WIND = "wind"        # 風  -> bonus (East/South/West/North)
    DRAGON = "dragon"    # 龍  -> bonus (Red/Green/White)
    FLOWER = "flower"    # 花  -> bonus (Plum/Orchid/Bamboo/Chrysanthemum)
    SEASON = "season"    # 季  -> bonus (Spring/Summer/Autumn/Winter)

    @property
    def is_numbered(self) -> bool:
        return self in (Suit.MAN, Suit.PIN, Suit.SOU)


# Pretty short labels used in the UI / debug output.
WIND_NAMES = ["East", "South", "West", "North"]
WIND_GLYPHS = ["東", "南", "西", "北"]
DRAGON_NAMES = ["Red", "Green", "White"]
DRAGON_GLYPHS = ["中", "發", "白"]
FLOWER_NAMES = ["Plum", "Orchid", "Bamboo", "Chrysanthemum"]
FLOWER_GLYPHS = ["梅", "蘭", "竹", "菊"]
SEASON_NAMES = ["Spring", "Summer", "Autumn", "Winter"]
SEASON_GLYPHS = ["春", "夏", "秋", "冬"]
SUIT_GLYPH = {Suit.MAN: "萬", Suit.PIN: "筒", Suit.SOU: "條"}


_SUIT_ORDER = {
    Suit.MAN: 0, Suit.PIN: 1, Suit.SOU: 2,
    Suit.WIND: 3, Suit.DRAGON: 4, Suit.FLOWER: 5, Suit.SEASON: 6,
}


@dataclass(frozen=True)
class Tile:
    """A single tile.  `value` is 1-9 for numbered suits, 0-based for bonuses."""
    suit: Suit
    value: int

    def __lt__(self, other: "Tile") -> bool:
        return (_SUIT_ORDER[self.suit], self.value) < (_SUIT_ORDER[other.suit], other.value)

    def __le__(self, other: "Tile") -> bool:
        return self == other or self < other

    # ----- predicates -----
    @property
    def is_numbered(self) -> bool:
        return self.suit.is_numbered

    @property
    def is_bonus(self) -> bool:
        return not self.suit.is_numbered

    @property
    def is_terminal(self) -> bool:
        return self.is_numbered and self.value in (1, 9)

    # ----- factories -----
    @classmethod
    def m(cls, n: int) -> "Tile":
        return cls(Suit.MAN, n)

    @classmethod
    def p(cls, n: int) -> "Tile":
        return cls(Suit.PIN, n)

    @classmethod
    def s(cls, n: int) -> "Tile":
        return cls(Suit.SOU, n)

    # ----- display -----
    @property
    def short(self) -> str:
        """Compact text form, e.g. '5m', 'E', 'Rd', 'Spr'."""
        if self.suit == Suit.MAN:
            return f"{self.value}m"
        if self.suit == Suit.PIN:
            return f"{self.value}p"
        if self.suit == Suit.SOU:
            return f"{self.value}s"
        if self.suit == Suit.WIND:
            return WIND_NAMES[self.value][0]               # E/S/W/N
        if self.suit == Suit.DRAGON:
            return DRAGON_NAMES[self.value][0] + "d"        # Rd/Gd/Wd
        if self.suit == Suit.FLOWER:
            return "F" + FLOWER_NAMES[self.value][:3]
        if self.suit == Suit.SEASON:
            return "S" + SEASON_NAMES[self.value][:3]
        return "?"

    @property
    def glyph(self) -> str:
        """Pretty CJK label suitable for tile artwork."""
        if self.suit.is_numbered:
            return f"{self.value}{SUIT_GLYPH[self.suit]}"
        if self.suit == Suit.WIND:
            return WIND_GLYPHS[self.value]
        if self.suit == Suit.DRAGON:
            return DRAGON_GLYPHS[self.value]
        if self.suit == Suit.FLOWER:
            return FLOWER_GLYPHS[self.value]
        if self.suit == Suit.SEASON:
            return SEASON_GLYPHS[self.value]
        return "?"

    def __repr__(self) -> str:
        return self.short

    # ----- serialisation for the network protocol -----
    def to_id(self) -> str:
        return f"{self.suit.value}:{self.value}"

    @classmethod
    def from_id(cls, s: str) -> "Tile":
        suit_str, val_str = s.split(":")
        return cls(Suit(suit_str), int(val_str))


# ---------------------------------------------------------------- canonical sets

def _build_all_tiles() -> List[Tile]:
    tiles: List[Tile] = []
    # 108 numbered: man/pin/sou 1-9, four copies each
    for suit in (Suit.MAN, Suit.PIN, Suit.SOU):
        for v in range(1, 10):
            for _ in range(4):
                tiles.append(Tile(suit, v))
    # 16 winds (4 winds x4)
    for v in range(4):
        for _ in range(4):
            tiles.append(Tile(Suit.WIND, v))
    # 12 dragons (3 dragons x4)
    for v in range(3):
        for _ in range(4):
            tiles.append(Tile(Suit.DRAGON, v))
    # 4 flowers (one of each)
    for v in range(4):
        tiles.append(Tile(Suit.FLOWER, v))
    # 4 seasons
    for v in range(4):
        tiles.append(Tile(Suit.SEASON, v))
    return tiles


ALL_TILES: List[Tile] = _build_all_tiles()
assert len(ALL_TILES) == 144, f"Expected 144 tiles, got {len(ALL_TILES)}"

PLAYABLE_TILES: List[Tile] = [t for t in ALL_TILES if t.is_numbered]
assert len(PLAYABLE_TILES) == 108

BONUS_TILES: List[Tile] = [t for t in ALL_TILES if t.is_bonus]
assert len(BONUS_TILES) == 36


# ---------------------------------------------------------------- gold tile

def gold_from_indicator(indicator: Tile) -> Tile:
    """
    Compute which tile-value is the Gold (Jin) wildcard, given the indicator.

    Convention: the Gold is the tile *after* the indicator in its suit.
    9 wraps around to 1.  Bonus tiles can also be revealed as indicator:
    - Winds:   E -> S -> W -> N -> E
    - Dragons: R -> G -> W -> R
    - Flowers/Seasons cycle within their group.
    """
    s, v = indicator.suit, indicator.value
    if s.is_numbered:
        return Tile(s, 1 if v == 9 else v + 1)
    if s == Suit.WIND:
        return Tile(s, (v + 1) % 4)
    if s == Suit.DRAGON:
        return Tile(s, (v + 1) % 3)
    if s in (Suit.FLOWER, Suit.SEASON):
        return Tile(s, (v + 1) % 4)
    raise ValueError(f"Unknown suit on indicator {indicator}")


# Sentinel for "no gold has been chosen yet" --- handy in tests
GOLD_TILE_INDICATOR: Optional[Tile] = None


# ---------------------------------------------------------------- helpers

def sorted_tiles(tiles: List[Tile]) -> List[Tile]:
    """Sort by suit-then-value the way a human would arrange a hand."""
    suit_order = {
        Suit.MAN: 0, Suit.PIN: 1, Suit.SOU: 2,
        Suit.WIND: 3, Suit.DRAGON: 4, Suit.FLOWER: 5, Suit.SEASON: 6,
    }
    return sorted(tiles, key=lambda t: (suit_order[t.suit], t.value))


def count_tile(tiles: List[Tile], target: Tile) -> int:
    return sum(1 for t in tiles if t == target)
