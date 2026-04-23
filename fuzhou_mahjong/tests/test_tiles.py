"""Tests for the tile model and the Gold-from-indicator rule."""
from fuzhou_mahjong.game import (
    ALL_TILES, BONUS_TILES, PLAYABLE_TILES, Suit, Tile, gold_from_indicator,
    sorted_tiles,
)


def test_full_set_has_144_tiles():
    assert len(ALL_TILES) == 144


def test_playable_set_has_108_numbered_tiles():
    assert len(PLAYABLE_TILES) == 108
    assert all(t.is_numbered for t in PLAYABLE_TILES)


def test_bonus_set_has_36_tiles_with_expected_distribution():
    assert len(BONUS_TILES) == 36
    winds = [t for t in BONUS_TILES if t.suit == Suit.WIND]
    dragons = [t for t in BONUS_TILES if t.suit == Suit.DRAGON]
    flowers = [t for t in BONUS_TILES if t.suit == Suit.FLOWER]
    seasons = [t for t in BONUS_TILES if t.suit == Suit.SEASON]
    assert len(winds) == 16     # 4 winds x 4 copies
    assert len(dragons) == 12   # 3 dragons x 4 copies
    assert len(flowers) == 4    # 1 of each flower
    assert len(seasons) == 4    # 1 of each season


def test_tile_identity_and_equality():
    assert Tile.m(5) == Tile(Suit.MAN, 5)
    assert Tile.p(3) != Tile.s(3)
    assert Tile.m(1).is_terminal
    assert not Tile.m(5).is_terminal


def test_tile_roundtrip_via_id_string():
    for t in (Tile.m(9), Tile.p(1), Tile.s(5), Tile(Suit.WIND, 2),
              Tile(Suit.DRAGON, 0), Tile(Suit.FLOWER, 3)):
        assert Tile.from_id(t.to_id()) == t


def test_sorted_tiles_orders_by_suit_then_value():
    mixed = [Tile.s(3), Tile.m(1), Tile.p(9), Tile.m(5), Tile(Suit.WIND, 0)]
    out = sorted_tiles(mixed)
    assert out == [Tile.m(1), Tile.m(5), Tile.p(9), Tile.s(3), Tile(Suit.WIND, 0)]


def test_tile_ordering_is_total():
    # Tiles must be comparable for sort() across mixed suits.
    xs = [Tile.s(1), Tile.m(9), Tile.p(5)]
    xs.sort()
    assert xs == [Tile.m(9), Tile.p(5), Tile.s(1)]


def test_gold_from_numbered_indicator_advances_by_one():
    assert gold_from_indicator(Tile.m(1)) == Tile.m(2)
    assert gold_from_indicator(Tile.p(8)) == Tile.p(9)
    assert gold_from_indicator(Tile.s(9)) == Tile.s(1)   # wraps 9 -> 1


def test_gold_from_wind_cycles():
    assert gold_from_indicator(Tile(Suit.WIND, 0)) == Tile(Suit.WIND, 1)
    assert gold_from_indicator(Tile(Suit.WIND, 3)) == Tile(Suit.WIND, 0)


def test_gold_from_dragon_cycles():
    assert gold_from_indicator(Tile(Suit.DRAGON, 0)) == Tile(Suit.DRAGON, 1)
    assert gold_from_indicator(Tile(Suit.DRAGON, 2)) == Tile(Suit.DRAGON, 0)
