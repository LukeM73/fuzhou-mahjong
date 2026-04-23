"""
The wall (deck) and dealing procedure for Fuzhou Mahjong.

Hand size:
  Each player ends up with 16 tiles in hand.  The dealer starts with 17
  (so they discard first to begin the cycle).  Tiles are dealt 4 at a time
  in turn-order until everyone has 16, then the dealer takes 1 extra.

Bonus replacement:
  Whenever a player draws or is dealt a bonus tile (winds / dragons /
  flowers / seasons), it is set aside in the player's flower rack and a
  replacement tile is drawn from the *back* of the wall (dead wall in
  classical mahjong; for simplicity we use the live wall here).

Gold tile:
  After the deal, a single tile is flipped from the wall as the indicator;
  the next-in-sequence tile of that suit is the Gold (Jin) wildcard.
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

from .tiles import ALL_TILES, Tile, gold_from_indicator


HAND_SIZE = 16
DEALER_HAND_SIZE = 17


class Deck:
    """A shuffled wall of tiles with simple draw / replace operations."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._tiles: List[Tile] = list(ALL_TILES)
        self._rng.shuffle(self._tiles)
        # The indicator + gold tile are determined when the round begins.
        self.indicator: Optional[Tile] = None
        self.gold: Optional[Tile] = None

    # ----- wall -----
    def __len__(self) -> int:
        return len(self._tiles)

    @property
    def remaining(self) -> int:
        return len(self._tiles)

    def draw(self) -> Optional[Tile]:
        """Draw from the front of the wall.  Returns None if exhausted."""
        if not self._tiles:
            return None
        return self._tiles.pop(0)

    def draw_replacement(self) -> Optional[Tile]:
        """
        Draw a replacement tile when a bonus is drawn.  We pull from the *back*
        of the wall, mirroring the dead-wall convention.
        """
        if not self._tiles:
            return None
        return self._tiles.pop()

    # ----- gold -----
    def reveal_gold(self) -> Tile:
        """Flip the indicator tile from the back of the wall and set the gold."""
        if self.gold is not None:
            return self.gold
        # Re-draw if the indicator itself is a bonus tile so the gold is
        # always a sensible wildcard --- usually a numbered tile.
        # (Some Fuzhou variants permit honour-tile golds; we keep the simple
        # rule of re-flip on bonus.)
        for _ in range(20):
            t = self._tiles.pop()
            if t.is_numbered:
                self.indicator = t
                break
            # discard the bonus and try again
        else:
            raise RuntimeError("Could not find a numbered indicator tile")
        self.gold = gold_from_indicator(self.indicator)
        return self.gold


# --------------------------------------------------------------------- dealing


def deal_round(
    seed: Optional[int] = None,
    n_players: int = 4,
    dealer_seat: int = 0,
) -> Tuple[Deck, List[List[Tile]], List[List[Tile]]]:
    """
    Shuffle a fresh deck and deal a Fuzhou Mahjong round.

    Returns:
        (deck, hands, flowers) where:
          hands[i]   = the 16 (or 17 for dealer) playable tiles for player i
          flowers[i] = the bonus tiles dealt to player i (already replaced)
    """
    deck = Deck(seed=seed)
    hands: List[List[Tile]] = [[] for _ in range(n_players)]
    flowers: List[List[Tile]] = [[] for _ in range(n_players)]

    # Deal 4 tiles at a time, replacing bonuses immediately.
    for _ in range(HAND_SIZE // 4):
        for offset in range(n_players):
            seat = (dealer_seat + offset) % n_players
            for _ in range(4):
                t = deck.draw()
                if t is None:
                    raise RuntimeError("wall exhausted during deal")
                _place(t, hands[seat], flowers[seat], deck)

    # Dealer's extra opening tile.
    t = deck.draw()
    if t is None:
        raise RuntimeError("wall exhausted before dealer extra tile")
    _place(t, hands[dealer_seat], flowers[dealer_seat], deck)

    # Reveal the gold tile after dealing is complete.
    deck.reveal_gold()

    return deck, hands, flowers


def _place(tile: Tile, hand: List[Tile], flower_rack: List[Tile], deck: Deck) -> None:
    """Place a freshly-drawn tile into a hand, replacing bonuses recursively."""
    while tile.is_bonus:
        flower_rack.append(tile)
        replacement = deck.draw_replacement()
        if replacement is None:
            return
        tile = replacement
    hand.append(tile)
