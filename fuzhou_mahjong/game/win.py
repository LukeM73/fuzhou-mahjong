"""
Win detection for Fuzhou (16-tile) Mahjong.

A winning hand is 5 sets + 1 pair = 17 tiles (kongs count as a single set but
contain 4 tiles; players with kongs have already drawn replacement tiles so
the logical hand size is always 5 sets + 1 pair).

The Gold (Jin) tile is a universal wildcard: it can fill any position in a
pair, pung, or chow.  For set decomposition we treat golds as a resource
count separate from the rest of the hand.

Special hands we detect here:
  * Three Golden Tiles  -- instant win on drawing 3rd gold (handled by state)
  * Golden Pair         -- the pair is two gold tiles (priority-breaker)
  * Golden Dragon       -- three golds used as a pung of their inherent value
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .melds import Meld, MeldType
from .tiles import Suit, Tile


@dataclass
class WinResult:
    is_win: bool = False
    pair: Optional[Tuple[Optional[Tile], int]] = None   # (tile, golds_in_pair)
    sets: List[Tuple[str, Optional[Tile], int]] = field(default_factory=list)
    #   (kind, anchor_tile_or_None, golds_in_set)
    golden_pair: bool = False
    golden_dragon: bool = False
    reason: str = ""

    def __bool__(self) -> bool:
        return self.is_win


# ---------------------------------------------------------------------------


def check_win(
    concealed: List[Tile],
    exposed: List[Meld],
    winning_tile: Optional[Tile],
    gold: Optional[Tile],
) -> WinResult:
    """Determine whether the given hand wins."""
    pool = list(concealed)
    if winning_tile is not None:
        pool.append(winning_tile)

    # A winning hand has 5 sets + pair (17 "logical" slots).  Each kong adds
    # one extra physical tile beyond that because the kong holder drew a
    # replacement.  So the expected total is 17 + (number of exposed kongs).
    n_kongs = sum(1 for m in exposed if m.is_kong)
    total = len(pool) + sum(4 if m.is_kong else 3 for m in exposed)
    if total != 17 + n_kongs:
        return WinResult(reason=f"wrong total tile count {total}")

    gold_count = 0
    rest: List[Tile] = []
    for t in pool:
        if gold is not None and t == gold:
            gold_count += 1
        else:
            rest.append(t)

    counter = Counter(rest)
    n_sets_needed = 5 - len(exposed)
    if n_sets_needed < 0:
        return WinResult(reason="too many exposed melds")

    # Try strategies in priority order so special-hand flags surface.
    strategies = []
    if gold_count >= 3:
        strategies.append("dragon_then_real_pair")
    if gold_count >= 2:
        strategies.append("gold_pair")
    strategies.append("regular")

    decomp = None
    for strat in strategies:
        decomp = _try_decompose(counter, gold_count, n_sets_needed, strat)
        if decomp is not None:
            break

    if decomp is None:
        return WinResult(reason="no valid decomposition")

    pair, sets_, golden_pair, golden_dragon = decomp

    # Combine exposed melds into the set list for the result.
    full_sets: List[Tuple[str, Optional[Tile], int]] = []
    for m in exposed:
        if m.type == MeldType.CHOW:
            anchor = min(m.tiles, key=lambda t: t.value)
            full_sets.append(("chow", anchor, 0))
        elif m.type == MeldType.PUNG:
            full_sets.append(("pung", m.tiles[0], 0))
        else:
            full_sets.append(("kong", m.tiles[0], 0))
    full_sets.extend(sets_)

    return WinResult(
        is_win=True,
        pair=pair,
        sets=full_sets,
        golden_pair=golden_pair,
        golden_dragon=golden_dragon,
        reason="ok",
    )


# ---------------------------------------------------------------- strategies


def _try_decompose(
    counter: Counter,
    golds: int,
    n_sets: int,
    strategy: str,
) -> Optional[Tuple[Tuple[Optional[Tile], int],
                    List[Tuple[str, Optional[Tile], int]],
                    bool, bool]]:
    """
    Attempt a specific high-level decomposition strategy.

    strategy:
      * "dragon_then_real_pair" -- 3 golds MUST form a pung; pair is real.
      * "gold_pair"             -- 2 golds MUST be the pair.
      * "regular"               -- any valid decomposition.
    """
    c = Counter({t: v for t, v in counter.items() if v > 0})

    if strategy == "dragon_then_real_pair":
        if golds < 3:
            return None
        # Try every possible real pair, then decompose the rest requiring
        # one 3-gold pung to be present.
        for t in list(c.keys()):
            if c[t] >= 2:
                c[t] -= 2
                rest = _decompose_sets(c, golds, n_sets, require_gold_dragon=True)
                c[t] += 2
                if rest is not None:
                    sets, _, gd = rest
                    return (t, 0), sets, False, True
        return None

    if strategy == "gold_pair":
        if golds < 2:
            return None
        sets_rest = _decompose_sets(c, golds - 2, n_sets, require_gold_dragon=False)
        if sets_rest is None:
            return None
        sets, gp, gd = sets_rest
        return (None, 2), sets, True, gd

    # regular
    return _decompose_general(c, golds, n_sets, need_pair=True)


def _decompose_general(
    counter: Counter,
    golds: int,
    n_sets: int,
    need_pair: bool,
) -> Optional[Tuple[Tuple[Optional[Tile], int],
                    List[Tuple[str, Optional[Tile], int]],
                    bool, bool]]:
    counter = Counter({t: v for t, v in counter.items() if v > 0})

    if need_pair:
        # Try real pairs first, then 1-real+1-gold pair, then 2-gold pair.
        for t in list(counter.keys()):
            if counter[t] >= 2:
                counter[t] -= 2
                rest = _decompose_sets(counter, golds, n_sets)
                counter[t] += 2
                if rest is not None:
                    sets, gp, gd = rest
                    return (t, 0), sets, False, gd
        if golds >= 1:
            for t in list(counter.keys()):
                if counter[t] >= 1:
                    counter[t] -= 1
                    rest = _decompose_sets(counter, golds - 1, n_sets)
                    counter[t] += 1
                    if rest is not None:
                        sets, gp, gd = rest
                        return (t, 1), sets, False, gd
        if golds >= 2:
            rest = _decompose_sets(counter, golds - 2, n_sets)
            if rest is not None:
                sets, gp, gd = rest
                return (None, 2), sets, True, gd
        return None

    rest = _decompose_sets(counter, golds, n_sets)
    if rest is None:
        return None
    sets, gp, gd = rest
    return (None, 0), sets, gp, gd


# ---------------------------------------------------------------- set decomposer


def _decompose_sets(
    counter: Counter,
    golds: int,
    n_sets: int,
    require_gold_dragon: bool = False,
) -> Optional[Tuple[List[Tuple[str, Optional[Tile], int]], bool, bool]]:
    """Split the remaining tiles + gold wildcards into exactly n_sets sets."""
    # Terminal case -- no real tiles left; remaining golds must form pungs.
    if sum(counter.values()) == 0:
        if n_sets == 0 and golds == 0:
            if require_gold_dragon:
                return None     # never placed the dragon pung
            return ([], False, False)
        if golds % 3 == 0 and golds // 3 == n_sets:
            sets = [("pung", None, 3)] * (golds // 3)
            if require_gold_dragon and golds < 3:
                return None
            # golden_dragon flag fires if a 3-gold pung was produced here.
            return (sets, False, golds >= 3)
        return None

    if n_sets == 0:
        return None

    smallest = min(t for t in counter if counter[t] > 0)

    # Option A: pungs anchored at `smallest`, with 0-3 golds.
    # Try g=3 first (Golden Dragon) to surface it cleanly.
    for g in range(min(3, golds), -1, -1):
        need_real = 3 - g
        if g == 3:
            # Pure-gold pung; does not consume `smallest`.
            rest = _decompose_sets(
                counter, golds - 3, n_sets - 1,
                require_gold_dragon=False,       # dragon satisfied here
            )
            if rest is not None:
                sets, gp, gd = rest
                sets = [("pung", None, 3), *sets]
                return sets, gp, True
            continue
        if counter[smallest] >= need_real:
            counter[smallest] -= need_real
            if counter[smallest] == 0:
                del counter[smallest]
            rest = _decompose_sets(
                counter, golds - g, n_sets - 1,
                require_gold_dragon=require_gold_dragon,
            )
            counter[smallest] = counter.get(smallest, 0) + need_real
            if rest is not None:
                sets, gp, gd = rest
                sets = [("pung", smallest, g), *sets]
                return sets, gp, gd

    # Option B: chow starting at `smallest`.
    if smallest.is_numbered and smallest.value <= 7:
        t1 = Tile(smallest.suit, smallest.value + 1)
        t2 = Tile(smallest.suit, smallest.value + 2)
        for g1 in (0, 1):
            for g2 in (0, 1):
                if g1 + g2 > golds:
                    continue
                if g1 == 0 and counter.get(t1, 0) == 0:
                    continue
                if g2 == 0 and counter.get(t2, 0) == 0:
                    continue
                counter[smallest] -= 1
                if counter[smallest] == 0:
                    del counter[smallest]
                if g1 == 0:
                    counter[t1] -= 1
                    if counter[t1] == 0:
                        del counter[t1]
                if g2 == 0:
                    counter[t2] -= 1
                    if counter[t2] == 0:
                        del counter[t2]

                rest = _decompose_sets(
                    counter, golds - g1 - g2, n_sets - 1,
                    require_gold_dragon=require_gold_dragon,
                )

                counter[smallest] = counter.get(smallest, 0) + 1
                if g1 == 0:
                    counter[t1] = counter.get(t1, 0) + 1
                if g2 == 0:
                    counter[t2] = counter.get(t2, 0) + 1

                if rest is not None:
                    sets, gp, gd = rest
                    sets = [("chow", smallest, g1 + g2), *sets]
                    return sets, gp, gd

    return None


# ---------------------------------------------------------------- waits / tenpai


def find_waits(
    concealed: List[Tile],
    exposed: List[Meld],
    gold: Optional[Tile],
    candidate_pool: Optional[List[Tile]] = None,
) -> List[Tile]:
    """Return every tile that, if drawn, would complete the hand."""
    from .tiles import PLAYABLE_TILES
    pool = candidate_pool if candidate_pool is not None else PLAYABLE_TILES
    seen = set()
    waits: List[Tile] = []
    for t in pool:
        if t in seen:
            continue
        seen.add(t)
        if check_win(concealed, exposed, t, gold).is_win:
            waits.append(t)
    return waits
