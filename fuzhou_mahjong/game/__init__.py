"""Game logic — pure Python, no UI/network dependencies."""
from .tiles import (
    Tile, Suit,
    ALL_TILES, PLAYABLE_TILES, BONUS_TILES,
    gold_from_indicator, sorted_tiles,
)
from .deck import Deck, HAND_SIZE, deal_round
from .hand import Hand
from .melds import (
    Meld, MeldType, Call,
    find_calls, find_concealed_kongs, find_promotable_kongs,
)
from .win import WinResult, check_win, find_waits
from .score import ScoreBreakdown, score_hand, format_breakdown, SPECIAL_HAND_POINTS
from .state import (
    GameState, Player, Action, ActionType, Event, EventType, Phase,
    start_new_game,
)

__all__ = [
    "Tile", "Suit", "ALL_TILES", "PLAYABLE_TILES", "BONUS_TILES",
    "gold_from_indicator", "sorted_tiles",
    "Deck", "HAND_SIZE", "deal_round",
    "Hand",
    "Meld", "MeldType", "Call",
    "find_calls", "find_concealed_kongs", "find_promotable_kongs",
    "WinResult", "check_win", "find_waits",
    "ScoreBreakdown", "score_hand", "format_breakdown", "SPECIAL_HAND_POINTS",
    "GameState", "Player", "Action", "ActionType", "Event", "EventType", "Phase",
    "start_new_game",
]
