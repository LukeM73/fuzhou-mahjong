"""Tests for the deck, dealing procedure, and gold reveal."""
from fuzhou_mahjong.game import Deck, HAND_SIZE, deal_round


def test_deck_contains_all_144_tiles_in_random_order():
    d1 = Deck(seed=0)
    d2 = Deck(seed=1)
    assert d1.remaining == 144
    # Two different seeds should produce different orderings (not a strict
    # guarantee, but with 144! possibilities the collision chance is ~0).
    first_five_1 = [d1.draw() for _ in range(5)]
    first_five_2 = [d2.draw() for _ in range(5)]
    assert first_five_1 != first_five_2


def test_deal_round_produces_16_tile_hands_for_non_dealers():
    deck, hands, flowers = deal_round(seed=42, dealer_seat=0)
    for seat, hand in enumerate(hands):
        expected = HAND_SIZE + (1 if seat == 0 else 0)
        assert len(hand) == expected, f"seat {seat} has {len(hand)}, expected {expected}"


def test_deal_round_reveals_a_gold_tile():
    deck, _, _ = deal_round(seed=7)
    assert deck.gold is not None
    assert deck.indicator is not None
    # The gold should be a numbered tile (re-flip on bonus indicator).
    assert deck.gold.is_numbered


def test_deal_round_all_tiles_accounted_for():
    """Total tiles across hands + flowers + wall must equal 144."""
    deck, hands, flowers = deal_round(seed=99, dealer_seat=2)
    dealt = sum(len(h) for h in hands) + sum(len(f) for f in flowers)
    # Account for the indicator tile pulled off the back of the wall.
    assert dealt + deck.remaining + 1 == 144


def test_deal_flowers_are_all_bonus_tiles():
    _, _, flowers = deal_round(seed=17)
    for rack in flowers:
        for t in rack:
            assert t.is_bonus


def test_deal_hand_tiles_are_all_numbered():
    _, hands, _ = deal_round(seed=31)
    for hand in hands:
        for t in hand:
            assert t.is_numbered, f"non-numbered tile {t} in hand"


def test_deck_seed_is_reproducible():
    d1 = Deck(seed=123)
    d2 = Deck(seed=123)
    assert [d1.draw() for _ in range(20)] == [d2.draw() for _ in range(20)]
