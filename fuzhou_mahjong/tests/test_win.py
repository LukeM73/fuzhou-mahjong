"""Tests for win detection -- the trickiest part of the engine.

A 16-tile Fuzhou hand wins with 5 sets + 1 pair (= 17 tiles counting the
winning tile).  The Gold is a universal wildcard.  Special flags:
  * golden_dragon  -- three golds form a pung
  * golden_pair    -- two golds form the pair
"""
from fuzhou_mahjong.game import (
    Meld, MeldType, Tile, check_win, find_waits,
)


def _make_meld(kind: MeldType, tiles):
    return Meld(kind, tiles, called_from_seat=None, claimed_tile=None)


# ------------------------------------------------------------------ basic wins


def test_plain_five_pungs_and_pair_is_a_win():
    # 5 pungs concealed + pair = 17 tiles exactly.
    concealed = (
        [Tile.m(1)] * 3 + [Tile.m(5)] * 3 + [Tile.p(3)] * 3 +
        [Tile.p(7)] * 3 + [Tile.s(2)] * 3 + [Tile.s(9)] * 2
    )
    winning_tile = concealed.pop()   # win-on-draw: last tile becomes winning
    r = check_win(concealed, exposed=[], winning_tile=winning_tile, gold=None)
    assert r.is_win, r.reason


def test_mixed_chows_and_pungs_win():
    # 2 chows + 3 pungs + pair
    concealed = (
        [Tile.m(1), Tile.m(2), Tile.m(3)] +
        [Tile.p(4), Tile.p(5), Tile.p(6)] +
        [Tile.s(7)] * 3 +
        [Tile(Tile.m(9).suit, 9)] * 3 +   # Tile.m(9)
        [Tile.p(1)] * 3 +
        [Tile.p(9), Tile.p(9)]
    )
    winning_tile = concealed.pop()
    r = check_win(concealed, exposed=[], winning_tile=winning_tile, gold=None)
    assert r.is_win, r.reason


def test_not_enough_tiles_fails():
    concealed = [Tile.m(1)] * 3
    r = check_win(concealed, exposed=[], winning_tile=None, gold=None)
    assert not r.is_win


def test_wrong_structure_fails():
    # 17 tiles but no valid decomposition (random clutter).
    concealed = [Tile.m(1), Tile.m(3), Tile.m(5), Tile.p(2), Tile.p(4),
                 Tile.p(6), Tile.s(1), Tile.s(3), Tile.s(5), Tile.m(7),
                 Tile.m(9), Tile.p(8), Tile.s(7), Tile.s(9), Tile.m(2),
                 Tile.p(1)]
    winning_tile = Tile.s(8)
    r = check_win(concealed, exposed=[], winning_tile=winning_tile, gold=None)
    assert not r.is_win


# ------------------------------------------------------------------ exposed melds


def test_win_with_exposed_meld():
    exposed = [_make_meld(MeldType.PUNG, [Tile.m(5)] * 3)]
    # Need 4 more sets + pair = 4*3 + 2 = 14 concealed tiles.
    concealed = (
        [Tile.p(1)] * 3 + [Tile.p(5)] * 3 +
        [Tile.s(2)] * 3 + [Tile.s(9)] * 3 +
        [Tile.m(7), Tile.m(7)]
    )
    winning_tile = concealed.pop()
    r = check_win(concealed, exposed=exposed, winning_tile=winning_tile, gold=None)
    assert r.is_win, r.reason


def test_win_with_exposed_kong_still_wins():
    exposed = [_make_meld(MeldType.KONG_EXPOSED, [Tile.m(1)] * 4)]
    concealed = (
        [Tile.p(2)] * 3 + [Tile.p(5)] * 3 +
        [Tile.s(3)] * 3 + [Tile.s(7)] * 3 +
        [Tile.m(9), Tile.m(9)]
    )
    winning_tile = concealed.pop()
    r = check_win(concealed, exposed=exposed, winning_tile=winning_tile, gold=None)
    assert r.is_win


# ------------------------------------------------------------------ gold wildcards


def test_one_gold_fills_a_pung():
    gold = Tile.p(5)
    # 4 real pungs + pair + (2 of P5 + gold) makes the 5th pung.
    concealed = (
        [Tile.m(1)] * 3 + [Tile.m(9)] * 3 +
        [Tile.s(2)] * 3 + [Tile.s(8)] * 3 +
        [Tile.p(5)] * 2 +
        [Tile.m(5), Tile.m(5)] + [gold]   # last two tiles = real pair + gold
    )
    assert len(concealed) == 17
    winning_tile = concealed.pop()       # winning the gold completes the hand
    r = check_win(concealed, exposed=[], winning_tile=winning_tile, gold=gold)
    assert r.is_win, r.reason


def test_one_gold_fills_a_chow():
    gold = Tile.p(5)
    concealed = (
        [Tile.m(1), Tile.m(2), Tile.m(3)] +
        [Tile.s(4), Tile.s(5), Tile.s(6)] +
        [Tile.m(5)] * 3 +
        [Tile.p(7)] * 3 +
        [Tile.s(9), Tile.s(9)] +
        [Tile.p(4), Tile.p(6)] + [gold]
    )
    assert len(concealed) == 17
    winning_tile = concealed.pop()
    r = check_win(concealed, exposed=[], winning_tile=winning_tile, gold=gold)
    assert r.is_win, r.reason


def test_golden_pair_special_flag():
    gold = Tile.p(9)
    # Two golds as the pair; 5 real sets elsewhere.
    concealed = (
        [Tile.m(1)] * 3 + [Tile.m(5)] * 3 +
        [Tile.p(3)] * 3 + [Tile.s(2)] * 3 +
        [Tile.s(8)] * 3 + [gold, gold]
    )
    winning_tile = concealed.pop()
    r = check_win(concealed, exposed=[], winning_tile=winning_tile, gold=gold)
    assert r.is_win
    assert r.golden_pair, "expected golden_pair flag"
    assert not r.golden_dragon


def test_golden_dragon_special_flag():
    gold = Tile.p(9)
    # Three golds as a pung; 4 real sets + real pair.
    concealed = (
        [Tile.m(1)] * 3 + [Tile.m(5)] * 3 +
        [Tile.p(3)] * 3 + [Tile.s(2)] * 3 +
        [gold, gold, gold] + [Tile.s(9), Tile.s(9)]
    )
    winning_tile = concealed.pop()
    r = check_win(concealed, exposed=[], winning_tile=winning_tile, gold=gold)
    assert r.is_win
    assert r.golden_dragon, "expected golden_dragon flag"


def test_golden_dragon_prefers_over_golden_pair():
    """With 3+ golds, Golden Dragon should trigger instead of Golden Pair."""
    gold = Tile.p(9)
    concealed = (
        [Tile.m(1)] * 3 + [Tile.m(5)] * 3 +
        [Tile.p(3)] * 3 + [Tile.s(2)] * 3 +
        [gold, gold, gold] + [Tile.s(9), Tile.s(9)]
    )
    winning_tile = concealed.pop()
    r = check_win(concealed, exposed=[], winning_tile=winning_tile, gold=gold)
    assert r.is_win
    assert r.golden_dragon
    # Can't be both -- the engine should exclusively flag dragon here.
    assert not r.golden_pair


# ------------------------------------------------------------------ tenpai / waits


def test_find_waits_returns_winning_tile_for_simple_hand():
    # Hand waiting on P5 to complete a pung.
    concealed = (
        [Tile.m(1)] * 3 + [Tile.m(5)] * 3 +
        [Tile.p(5)] * 2 + [Tile.s(3)] * 3 +
        [Tile.s(8)] * 3 + [Tile.p(9), Tile.p(9)]
    )
    assert len(concealed) == 16
    waits = find_waits(concealed, exposed=[], gold=None)
    assert Tile.p(5) in waits


def test_no_waits_when_hand_is_shape_broken():
    concealed = [Tile.m(1), Tile.m(3), Tile.m(5), Tile.m(7), Tile.m(9),
                 Tile.p(2), Tile.p(4), Tile.p(6), Tile.p(8),
                 Tile.s(1), Tile.s(3), Tile.s(5), Tile.s(7), Tile.s(9),
                 Tile.m(2), Tile.p(1)]
    assert len(concealed) == 16
    waits = find_waits(concealed, exposed=[], gold=None)
    # Gap-filled alternating tiles won't form 5 sets + pair.
    assert waits == []
