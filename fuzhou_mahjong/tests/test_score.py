"""Tests for Fuzhou scoring formula and special-hand bonuses."""
from fuzhou_mahjong.game import (
    Hand, Meld, MeldType, Suit, Tile,
    WinResult, score_hand, SPECIAL_HAND_POINTS, check_win,
)


def _simple_hand(concealed=None, melds=None, flowers=None):
    h = Hand()
    h.concealed = list(concealed or [])
    h.melds = list(melds or [])
    h.flowers = list(flowers or [])
    return h


def test_base_score_formula_plain_hand():
    """No flowers, no golds, no dealer streak, no kongs.  Subtotal = 5*2 = 10."""
    hand = _simple_hand(
        concealed=([Tile.m(1)] * 3 + [Tile.m(5)] * 3 + [Tile.p(3)] * 3 +
                   [Tile.p(7)] * 3 + [Tile.s(5)] * 3 + [Tile.s(2)] * 2),
    )
    # 5 pungs + pair waiting on S2 to complete -- actually already complete.
    # Use the last S2 as the winning tile.
    hand.concealed.pop()
    winning_tile = Tile.s(2)
    win = check_win(hand.concealed, hand.melds, winning_tile, gold=None)
    assert win.is_win
    hand.concealed.append(winning_tile)
    b = score_hand(hand, win, gold=None, dealer_streak=0, self_draw=True)
    assert b.base == 5
    assert b.flower_fan == 0
    assert b.gold_fan == 0
    assert b.dealer_continuation == 0
    assert b.kong_fan == 0
    assert b.subtotal == 10
    # Plain all-pung hand => "all_triplets" bonus.
    assert "all_triplets" in b.specials


def test_flower_fan_one_per_tile():
    flowers = [Tile(Suit.FLOWER, 0), Tile(Suit.FLOWER, 1), Tile(Suit.SEASON, 2)]
    hand = _simple_hand(
        concealed=([Tile.m(1)] * 3 + [Tile.m(5)] * 3 + [Tile.p(3)] * 3 +
                   [Tile.p(7)] * 3 + [Tile.s(5)] * 3 + [Tile.s(2)] * 2),
        flowers=flowers,
    )
    hand.concealed.pop()
    winning_tile = Tile.s(2)
    win = check_win(hand.concealed, hand.melds, winning_tile, gold=None)
    hand.concealed.append(winning_tile)
    b = score_hand(hand, win, gold=None, dealer_streak=0, self_draw=True)
    assert b.flower_fan == 3


def test_full_flower_set_bonus_applied():
    # All four seasons = full_flower_set.
    flowers = [Tile(Suit.SEASON, v) for v in range(4)]
    hand = _simple_hand(
        concealed=([Tile.m(1)] * 3 + [Tile.m(5)] * 3 + [Tile.p(3)] * 3 +
                   [Tile.p(7)] * 3 + [Tile.s(5)] * 3 + [Tile.s(2)] * 2),
        flowers=flowers,
    )
    hand.concealed.pop()
    winning_tile = Tile.s(2)
    win = check_win(hand.concealed, hand.melds, winning_tile, gold=None)
    hand.concealed.append(winning_tile)
    b = score_hand(hand, win, gold=None, dealer_streak=0, self_draw=True)
    # 4 tiles (+1 each) + bonus of +2 for the full set = 6 fan.
    assert b.flower_fan == 6


def test_gold_fan_counts_gold_tiles_in_hand():
    # Gold is a tile that doesn't appear elsewhere in the hand so we can
    # count exactly how many gold wildcards we used.
    gold = Tile.s(1)
    concealed = (
        [Tile.m(1)] * 3 + [Tile.m(9)] * 3 +
        [Tile.p(5)] * 3 + [Tile.s(8)] * 3 +
        [Tile.p(3), Tile.p(3)] + [Tile.s(5), Tile.s(5)] + [gold]
    )
    assert len(concealed) == 17
    winning_tile = concealed.pop()  # winning_tile = gold
    win = check_win(concealed, [], winning_tile, gold=gold)
    assert win.is_win, win.reason
    concealed.append(winning_tile)
    hand = _simple_hand(concealed=concealed)
    b = score_hand(hand, win, gold=gold, dealer_streak=0, self_draw=True)
    # Exactly one gold tile appears in the final hand.
    assert b.gold_fan == 1


def test_kong_fan_doubled_for_concealed_kong():
    """Exposed kong = +1 fan; concealed kong = +2 fan."""
    exposed_kong = Meld(MeldType.KONG_EXPOSED, [Tile.m(1)] * 4,
                        called_from_seat=1, claimed_tile=Tile.m(1))
    concealed_kong = Meld(MeldType.KONG_CONCEALED, [Tile.s(9)] * 4)
    # 3 pungs + pair + 2 kongs = 5 sets + pair
    concealed = (
        [Tile.p(2)] * 3 + [Tile.p(5)] * 3 +
        [Tile.m(3)] * 3 + [Tile.p(8)]
    )
    winning_tile = Tile.p(8)
    win = check_win(concealed, [exposed_kong, concealed_kong],
                    winning_tile, gold=None)
    assert win.is_win, win.reason
    concealed.append(winning_tile)
    hand = _simple_hand(concealed=concealed,
                        melds=[exposed_kong, concealed_kong])
    b = score_hand(hand, win, gold=None, dealer_streak=0, self_draw=True)
    assert b.kong_fan == 1 + 2   # 1 for exposed + 2 for concealed


def _five_pung_hand():
    """Helper: a complete 5-pung + pair hand, pre-pop winning tile."""
    h = _simple_hand(
        concealed=([Tile.m(1)] * 3 + [Tile.m(5)] * 3 + [Tile.p(3)] * 3 +
                   [Tile.p(7)] * 3 + [Tile.s(5)] * 3 + [Tile.s(2)] * 2),
    )
    h.concealed.pop()
    return h


def test_dealer_continuation_adds_fan():
    hand = _five_pung_hand()
    winning_tile = Tile.s(2)
    win = check_win(hand.concealed, [], winning_tile, gold=None)
    hand.concealed.append(winning_tile)
    b = score_hand(hand, win, gold=None, dealer_streak=2, self_draw=True)
    assert b.dealer_continuation == 2
    assert b.subtotal == (5 + 0 + 0 + 2 + 0) * 2   # = 14


def test_self_draw_paid_by_three_discard_win_paid_by_one():
    hand = _five_pung_hand()
    winning_tile = Tile.s(2)
    win = check_win(hand.concealed, [], winning_tile, gold=None)
    hand.concealed.append(winning_tile)

    b_self = score_hand(hand, win, gold=None, self_draw=True)
    b_disc = score_hand(hand, win, gold=None, self_draw=False)
    assert b_self.total_from_losers == b_self.payout_each * 3
    assert b_disc.total_from_losers == b_disc.payout_each * 1


def test_golden_dragon_bonus_applied():
    gold = Tile.p(9)
    concealed = (
        [Tile.m(1)] * 3 + [Tile.m(5)] * 3 +
        [Tile.p(3)] * 3 + [Tile.s(2)] * 3 +
        [gold, gold, gold] + [Tile.s(9), Tile.s(9)]
    )
    winning_tile = concealed.pop()
    win = check_win(concealed, [], winning_tile, gold=gold)
    assert win.is_win
    assert win.golden_dragon
    concealed.append(winning_tile)
    hand = _simple_hand(concealed=concealed)
    b = score_hand(hand, win, gold=gold, self_draw=True)
    assert "golden_dragon" in b.specials
    assert b.specials["golden_dragon"] == SPECIAL_HAND_POINTS["golden_dragon"]
