"""Tests for call detection (chow / pung / kong) and Fuzhou-specific rules."""
from fuzhou_mahjong.game import (
    MeldType, Tile, find_calls, find_concealed_kongs, find_promotable_kongs,
    Meld,
)


def test_pung_call_when_two_matching_tiles_in_hand():
    hand = [Tile.m(5), Tile.m(5), Tile.p(1), Tile.s(9)]
    calls = find_calls(hand, discard=Tile.m(5), is_next_player=False, gold=None)
    types = [c.type for c in calls]
    assert MeldType.PUNG in types
    assert MeldType.KONG_EXPOSED not in types


def test_kong_call_when_three_matching_tiles_in_hand():
    hand = [Tile.m(5), Tile.m(5), Tile.m(5), Tile.p(1)]
    calls = find_calls(hand, discard=Tile.m(5), is_next_player=False, gold=None)
    types = [c.type for c in calls]
    assert MeldType.PUNG in types
    assert MeldType.KONG_EXPOSED in types


def test_chow_call_only_from_next_player():
    hand = [Tile.m(4), Tile.m(6), Tile.p(1)]
    # Not next player: only pungs/kongs would apply, no chow.
    calls = find_calls(hand, discard=Tile.m(5), is_next_player=False, gold=None)
    assert all(c.type != MeldType.CHOW for c in calls)
    # Next player: chow should appear.
    calls_next = find_calls(hand, discard=Tile.m(5), is_next_player=True, gold=None)
    assert any(c.type == MeldType.CHOW for c in calls_next)


def test_chow_call_enumerates_all_three_positions():
    hand = [Tile.m(3), Tile.m(4), Tile.m(6), Tile.m(7)]
    calls = find_calls(hand, discard=Tile.m(5), is_next_player=True, gold=None)
    chow_tiles = sorted([tuple(sorted(t.value for t in c.tiles_from_hand))
                         for c in calls if c.type == MeldType.CHOW])
    # Possible: 3-4-5, 4-5-6, 5-6-7
    assert (3, 4) in chow_tiles
    assert (4, 6) in chow_tiles
    assert (6, 7) in chow_tiles


def test_chow_respects_suit_boundary():
    # 9m has no higher numbered neighbour, only (7,8) is valid below.
    hand = [Tile.m(7), Tile.m(8)]
    calls = find_calls(hand, discard=Tile.m(9), is_next_player=True, gold=None)
    chow_calls = [c for c in calls if c.type == MeldType.CHOW]
    assert len(chow_calls) == 1
    assert sorted(c.value for c in chow_calls[0].tiles_from_hand) == [7, 8]


def test_discarded_gold_cannot_be_called():
    hand = [Tile.m(5), Tile.m(5)]
    # Gold is 5m and someone discards it -- nobody can claim.
    calls = find_calls(hand, discard=Tile.m(5),
                       is_next_player=True, gold=Tile.m(5))
    assert calls == []


def test_bonus_discards_cannot_be_called():
    from fuzhou_mahjong.game import Suit
    hand = [Tile(Suit.WIND, 0), Tile(Suit.WIND, 0)]
    calls = find_calls(hand, discard=Tile(Suit.WIND, 0),
                       is_next_player=True, gold=None)
    assert calls == []


def test_find_concealed_kongs_spots_four_of_a_kind():
    hand = [Tile.m(3)] * 4 + [Tile.p(1), Tile.s(7)]
    assert find_concealed_kongs(hand) == [Tile.m(3)]


def test_find_concealed_kongs_ignores_three_of_a_kind():
    hand = [Tile.m(3)] * 3 + [Tile.p(1)]
    assert find_concealed_kongs(hand) == []


def test_find_promotable_kongs_from_existing_pung():
    pung = Meld(MeldType.PUNG, [Tile.m(5), Tile.m(5), Tile.m(5)],
                called_from_seat=1, claimed_tile=Tile.m(5))
    hand = [Tile.m(5), Tile.p(2)]
    assert find_promotable_kongs(hand, [pung]) == [Tile.m(5)]


def test_find_promotable_kongs_ignores_pung_without_fourth_tile_in_hand():
    pung = Meld(MeldType.PUNG, [Tile.m(5), Tile.m(5), Tile.m(5)],
                called_from_seat=1, claimed_tile=Tile.m(5))
    hand = [Tile.p(2)]
    assert find_promotable_kongs(hand, [pung]) == []
