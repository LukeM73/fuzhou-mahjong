"""
Fuzhou Mahjong scoring.

Payout formula (from the Mahjong Pros guide):

    subtotal = (Base + FlowerFan + GoldFan + DealerContinuation + KongFan) * 2
    payout   = subtotal + SpecialHandBonus

Where:
  Base                 = 5
  FlowerFan            = 1 per flower tile in the rack
                         (+ bonus 6 for a "set of four" of the same group)
  GoldFan              = 1 per Gold tile in the final hand
  DealerContinuation   = the dealer's consecutive-win streak
  KongFan              = 1 per exposed kong + 2 per concealed kong
                         (only kongs declared by the WINNER count)
  SpecialHandBonus     = see SPECIAL_HAND_POINTS below

Self-draw wins are paid by all three losers; discard wins are paid only by
the discarder.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .hand import Hand
from .melds import MeldType
from .tiles import Suit, Tile
from .win import WinResult


# Special hand bonuses (in base points).  Values chosen to echo the guide.
SPECIAL_HAND_POINTS = {
    "all_sequences": 15,       # Ping Hu / all chows (no pungs/kongs except maybe concealed?)
    "all_triplets": 20,        # all pungs/kongs
    "all_concealed": 10,       # no exposed melds
    "one_suit": 20,            # flush (single numbered suit only)
    "three_golden_tiles": 40,  # instant win -- handled in state machine
    "golden_dragon": 30,       # 3 golds form a pung
    "golden_pair": 10,         # 2 golds as pair (priority-breaker, small bonus)
    "seven_flowers": 20,       # 7+ flowers in rack (rare, celebratory)
    "full_flower_set": 10,     # a set of 4 matching flowers/seasons/winds
}


@dataclass
class ScoreBreakdown:
    base: int = 5
    flower_fan: int = 0
    gold_fan: int = 0
    dealer_continuation: int = 0
    kong_fan: int = 0
    specials: Dict[str, int] = field(default_factory=dict)   # name -> points
    subtotal: int = 0
    special_bonus: int = 0
    payout_each: int = 0      # per-loser payout (self-draw: each; discard: discarder)
    self_draw: bool = False
    total_from_losers: int = 0
    notes: List[str] = field(default_factory=list)


# -------------------------------------------------------------- helpers


def _count_flower_fan(flowers: List[Tile]) -> (int, List[str]):
    """
    Score flowers.  Each flower tile = 1 fan.  Additionally, a full set of 4
    same-group tiles (e.g. all four Seasons or all four Winds) scores 6 fan
    instead of the plain 4, and flags a "full_flower_set" bonus.
    """
    notes = []
    fan = len(flowers)

    # Check for full sets of 4 in each bonus-suit group.
    groups = {}
    for t in flowers:
        groups.setdefault(t.suit, set()).add(t.value)

    bonuses = 0
    for suit, values in groups.items():
        # Four-of-a-group -- e.g. all 4 seasons (values 0..3) or all four of
        # one wind at 4 copies (we only score the unique-group case here).
        if suit in (Suit.FLOWER, Suit.SEASON) and len(values) == 4:
            bonuses += 1
            notes.append(f"full set of {suit.value}")
    return fan + bonuses * 2, notes   # +2 so total is 4(tiles)+2 = 6


def _count_gold_fan(hand: Hand, gold: Optional[Tile]) -> int:
    if gold is None:
        return 0
    n = sum(1 for t in hand.concealed if t == gold)
    for m in hand.melds:
        for t in m.tiles:
            if t == gold:
                n += 1
    return n


def _count_kong_fan(hand: Hand) -> int:
    fan = 0
    for m in hand.melds:
        if m.type == MeldType.KONG_CONCEALED:
            fan += 2
        elif m.is_kong:
            fan += 1
    return fan


def _detect_special_hands(
    hand: Hand,
    win: WinResult,
    gold_count: int,
) -> Dict[str, int]:
    """Detect non-structural special hands and return {name: points}."""
    specials: Dict[str, int] = {}

    # Three gold tiles in hand = instant win special.
    if gold_count >= 3 and not win.golden_dragon:
        # (Three-gold instant win handled by state machine, but if we get here
        # with 3+ golds and no dragon flag, still award it.)
        specials["three_golden_tiles"] = SPECIAL_HAND_POINTS["three_golden_tiles"]

    if win.golden_dragon:
        specials["golden_dragon"] = SPECIAL_HAND_POINTS["golden_dragon"]
    elif win.golden_pair:
        specials["golden_pair"] = SPECIAL_HAND_POINTS["golden_pair"]

    # Structural specials from the full set list.
    all_chow = all(s[0] == "chow" for s in win.sets)
    all_trip = all(s[0] in ("pung", "kong") for s in win.sets)
    concealed = not any(
        (m.type in (MeldType.CHOW, MeldType.PUNG, MeldType.KONG_EXPOSED,
                    MeldType.KONG_PROMOTED)) for m in hand.melds
    )
    if all_chow:
        specials["all_sequences"] = SPECIAL_HAND_POINTS["all_sequences"]
    if all_trip:
        specials["all_triplets"] = SPECIAL_HAND_POINTS["all_triplets"]
    if concealed:
        specials["all_concealed"] = SPECIAL_HAND_POINTS["all_concealed"]

    # One-suit (single numbered suit only, ignoring gold pungs).
    suits_seen = set()
    for kind, anchor, _golds in win.sets:
        if anchor is not None and anchor.is_numbered:
            suits_seen.add(anchor.suit)
    if win.pair is not None and win.pair[0] is not None and win.pair[0].is_numbered:
        suits_seen.add(win.pair[0].suit)
    if len(suits_seen) == 1:
        specials["one_suit"] = SPECIAL_HAND_POINTS["one_suit"]

    if len(hand.flowers) >= 7:
        specials["seven_flowers"] = SPECIAL_HAND_POINTS["seven_flowers"]

    return specials


# -------------------------------------------------------------- public API


def score_hand(
    winner: Hand,
    win: WinResult,
    gold: Optional[Tile],
    dealer_streak: int = 0,
    self_draw: bool = True,
) -> ScoreBreakdown:
    """Compute the points the winner collects from each loser."""
    b = ScoreBreakdown(self_draw=self_draw)

    flower_fan, flower_notes = _count_flower_fan(winner.flowers)
    b.flower_fan = flower_fan
    b.notes.extend(flower_notes)

    gold_count = _count_gold_fan(winner, gold)
    b.gold_fan = gold_count
    b.kong_fan = _count_kong_fan(winner)
    b.dealer_continuation = dealer_streak

    b.subtotal = (
        b.base + b.flower_fan + b.gold_fan + b.dealer_continuation + b.kong_fan
    ) * 2

    b.specials = _detect_special_hands(winner, win, gold_count)
    b.special_bonus = sum(b.specials.values())

    b.payout_each = b.subtotal + b.special_bonus
    b.total_from_losers = b.payout_each * (3 if self_draw else 1)
    return b


def format_breakdown(b: ScoreBreakdown) -> str:
    """Pretty-print a breakdown for the UI / chat log."""
    lines = [
        f"Base {b.base}  + Flowers {b.flower_fan}  + Gold {b.gold_fan}"
        f"  + Dealer {b.dealer_continuation}  + Kongs {b.kong_fan}",
        f"  x 2 = {b.subtotal}",
    ]
    for name, pts in b.specials.items():
        lines.append(f"+ {name} ({pts})")
    lines.append(
        f"= {b.payout_each} per loser  "
        f"({'self-draw' if b.self_draw else 'discard'}; "
        f"total collected {b.total_from_losers})"
    )
    return "\n".join(lines)
