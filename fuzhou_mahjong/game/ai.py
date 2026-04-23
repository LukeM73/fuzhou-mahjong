"""
A small heuristic AI — good enough for testing and as seat-fill.

Strategy:
  * If the hand can win, declare.
  * On our turn, discard the tile that keeps us closest to tenpai
    (fewest tiles-away-from-winning).
  * When the call window opens on someone else's discard, only claim
    chow/pung if it doesn't worsen our shanten.
  * Always declare concealed kongs; never promote kongs (simpler).

Not a strong player -- the point is just to get a full round to run
end-to-end so we can smoke-test the engine.
"""
from __future__ import annotations

import random
from typing import List, Optional

from .melds import Call, MeldType, find_concealed_kongs
from .state import Action, ActionType, GameState
from .tiles import PLAYABLE_TILES, Tile
from .win import check_win, find_waits


def _shanten(concealed: List[Tile], exposed, gold: Optional[Tile]) -> int:
    """Rough 'tiles away from win' estimate -- 0 means tenpai."""
    waits = find_waits(concealed, exposed, gold)
    if waits:
        return 0
    # crude: count unmatched singletons.
    from collections import Counter
    c = Counter(concealed)
    singletons = sum(1 for _, v in c.items() if v == 1)
    return max(1, singletons // 2)


class AIPlayer:
    def __init__(self, seat: int, seed: Optional[int] = None):
        self.seat = seat
        self._rng = random.Random(seed)

    # ------------------------------------------------ decisions

    def act_on_turn(self, gs: GameState) -> Action:
        """Decide what to do when it's our turn to act."""
        p = gs.players[self.seat]

        # 1. Self-draw win?
        win_tile = p.hand.last_draw
        if win_tile is not None:
            temp = list(p.hand.concealed)
            temp.remove(win_tile)
            if check_win(temp, p.hand.melds, win_tile, gs.gold).is_win:
                return Action(ActionType.DECLARE_WIN, seat=self.seat,
                              tile=win_tile)

        # 2. Concealed kong if available.
        kongs = find_concealed_kongs(p.hand.concealed)
        if kongs:
            return Action(ActionType.KONG_CONCEALED, seat=self.seat,
                          tile=kongs[0])

        # 3. Pick the discard that minimises shanten.
        best, best_tile = None, None
        for t in set(p.hand.concealed):
            trial = list(p.hand.concealed)
            trial.remove(t)
            s = _shanten(trial, p.hand.melds, gs.gold)
            if best is None or s < best:
                best, best_tile = s, t
        if best_tile is None:
            best_tile = p.hand.concealed[-1]
        return Action(ActionType.DISCARD, seat=self.seat, tile=best_tile)

    def act_on_call(self, gs: GameState, calls: List[Call]) -> Action:
        """When someone else discards and we may call."""
        p = gs.players[self.seat]
        discard = gs.last_discard
        if discard is None:
            return Action(ActionType.PASS, seat=self.seat)

        # 1. Win-on-discard?
        if check_win(p.hand.concealed, p.hand.melds, discard, gs.gold).is_win:
            return Action(ActionType.DECLARE_WIN, seat=self.seat, tile=discard)

        # 2. Best non-win call: prefer pung over chow.
        non_win = [c for c in calls if c.tiles_from_hand]
        pungs = [c for c in non_win if c.type == MeldType.PUNG]
        if pungs:
            c = pungs[0]
            return Action(
                ActionType.CALL, seat=self.seat,
                meld_type=c.type,
                tiles_from_hand=list(c.tiles_from_hand),
            )
        # Occasionally take a chow.
        chows = [c for c in non_win if c.type == MeldType.CHOW]
        if chows and self._rng.random() < 0.3:
            c = chows[0]
            return Action(
                ActionType.CALL, seat=self.seat,
                meld_type=c.type,
                tiles_from_hand=list(c.tiles_from_hand),
            )
        return Action(ActionType.PASS, seat=self.seat)
