"""
Fuzhou Mahjong game state machine.

Responsibilities
----------------
* Own the deck, all 4 player hands, the flower racks, and the discard pile.
* Track whose turn it is and what phase the turn is in
  (waiting-for-draw -> waiting-for-discard -> waiting-for-calls).
* Accept player Actions (draw / discard / declare-kong / call-chow / call-pung
  / call-kong / declare-win / pass) and validate them.
* Emit Events so the UI / network layer can render them.

The state machine is deterministic given the RNG seed, so it can run on the
server and each client receives the same sequence of events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .deck import Deck, HAND_SIZE, deal_round
from .hand import Hand
from .melds import (
    Call,
    Meld,
    MeldType,
    find_calls,
    find_concealed_kongs,
    find_promotable_kongs,
)
from .score import ScoreBreakdown, score_hand
from .tiles import Tile
from .win import WinResult, check_win


# =============================================================== Actions


class ActionType(Enum):
    DRAW = "draw"
    DISCARD = "discard"
    CALL = "call"                  # chow / pung / exposed-kong on discard
    KONG_CONCEALED = "kong_concealed"
    KONG_PROMOTED = "kong_promoted"
    DECLARE_WIN = "declare_win"
    PASS = "pass"


@dataclass
class Action:
    type: ActionType
    seat: int
    tile: Optional[Tile] = None          # discard tile / kong tile / win tile
    meld_type: Optional[MeldType] = None # for CALL actions
    tiles_from_hand: Optional[List[Tile]] = None   # for CALL chow/pung/kong


# =============================================================== Events


class EventType(Enum):
    ROUND_START = "round_start"
    GOLD_REVEALED = "gold_revealed"
    DEAL = "deal"
    DRAW = "draw"
    DISCARD = "discard"
    CALL = "call"
    KONG = "kong"
    WIN = "win"
    DRAW_GAME = "draw_game"        # exhaustive draw (wall empty, no winner)
    ROUND_END = "round_end"


@dataclass
class Event:
    type: EventType
    seat: Optional[int] = None
    data: Dict = field(default_factory=dict)


# =============================================================== Players


@dataclass
class Player:
    seat: int
    name: str = ""
    hand: Hand = field(default_factory=Hand)
    score: int = 0       # accumulated across hands
    is_bot: bool = False


# =============================================================== Game


class Phase(Enum):
    WAITING_DRAW = "waiting_draw"        # current seat must draw
    WAITING_DISCARD = "waiting_discard"  # current seat must discard
    WAITING_CALLS = "waiting_calls"      # other seats may call/pass
    ROUND_OVER = "round_over"


@dataclass
class GameState:
    players: List[Player]
    dealer_seat: int = 0
    round_number: int = 0
    dealer_streak: int = 0
    phase: Phase = Phase.WAITING_DRAW
    current_seat: int = 0
    last_discard: Optional[Tile] = None
    last_discarder: Optional[int] = None
    discards: List[List[Tile]] = field(default_factory=lambda: [[] for _ in range(4)])
    deck: Optional[Deck] = None
    events: List[Event] = field(default_factory=list)
    winning_player: Optional[int] = None
    winning_breakdown: Optional[ScoreBreakdown] = None
    pending_calls: Dict[int, List[Call]] = field(default_factory=dict)
    pending_win_claim: Optional[int] = None

    # ---------------------------------------------------------- construction

    @classmethod
    def new_game(cls, player_names: List[str], seed: Optional[int] = None,
                 dealer_seat: int = 0) -> "GameState":
        assert len(player_names) == 4, "Fuzhou Mahjong is 4-player"
        players = [Player(seat=i, name=player_names[i]) for i in range(4)]
        gs = cls(players=players, dealer_seat=dealer_seat)
        gs.start_round(seed=seed)
        return gs

    # ---------------------------------------------------------- round lifecycle

    def start_round(self, seed: Optional[int] = None) -> None:
        self.round_number += 1
        self.deck, hands, flowers = deal_round(
            seed=seed, n_players=4, dealer_seat=self.dealer_seat,
        )
        for i, p in enumerate(self.players):
            p.hand = Hand(concealed=hands[i], flowers=flowers[i])
        self.discards = [[] for _ in range(4)]
        self.current_seat = self.dealer_seat
        self.last_discard = None
        self.last_discarder = None
        self.winning_player = None
        self.winning_breakdown = None
        self.pending_calls = {}
        self.pending_win_claim = None
        self.events = []
        self.events.append(Event(EventType.ROUND_START,
                                 data={"dealer": self.dealer_seat,
                                       "round": self.round_number}))
        self.events.append(Event(EventType.GOLD_REVEALED,
                                 data={"indicator": self.deck.indicator,
                                       "gold": self.deck.gold}))
        for i, p in enumerate(self.players):
            self.events.append(Event(
                EventType.DEAL, seat=i,
                data={"n_tiles": len(p.hand.concealed),
                      "flowers": list(p.hand.flowers)},
            ))
        # The dealer already has their opening tile -- they discard first.
        self.phase = Phase.WAITING_DISCARD

    # ---------------------------------------------------------- helpers

    @property
    def gold(self) -> Optional[Tile]:
        return self.deck.gold if self.deck else None

    def next_seat(self, seat: int) -> int:
        return (seat + 1) % 4

    # ---------------------------------------------------------- action API

    def legal_actions(self, seat: int) -> List[ActionType]:
        """Rough list of what `seat` can legally do right now."""
        if self.phase == Phase.ROUND_OVER:
            return []
        if self.phase == Phase.WAITING_DRAW and seat == self.current_seat:
            return [ActionType.DRAW]
        if self.phase == Phase.WAITING_DISCARD and seat == self.current_seat:
            acts = [ActionType.DISCARD]
            p = self.players[seat]
            # Self-draw win?
            last = p.hand.last_draw or (
                p.hand.concealed[-1] if p.hand.concealed else None
            )
            # We allow win declaration when holding the tile in hand.
            acts.append(ActionType.DECLARE_WIN)
            if find_concealed_kongs(p.hand.concealed):
                acts.append(ActionType.KONG_CONCEALED)
            if find_promotable_kongs(p.hand.concealed, p.hand.melds):
                acts.append(ActionType.KONG_PROMOTED)
            return acts
        if self.phase == Phase.WAITING_CALLS:
            acts = [ActionType.PASS]
            if seat in self.pending_calls and self.pending_calls[seat]:
                acts.append(ActionType.CALL)
            # Robbing-the-kong / discard-win is allowed anywhere
            return acts
        return []

    def apply(self, action: Action) -> List[Event]:
        """Apply an action and return the events generated."""
        before = len(self.events)
        if action.type == ActionType.DRAW:
            self._do_draw(action)
        elif action.type == ActionType.DISCARD:
            self._do_discard(action)
        elif action.type == ActionType.CALL:
            self._do_call(action)
        elif action.type == ActionType.KONG_CONCEALED:
            self._do_kong_concealed(action)
        elif action.type == ActionType.KONG_PROMOTED:
            self._do_kong_promoted(action)
        elif action.type == ActionType.DECLARE_WIN:
            self._do_win(action)
        elif action.type == ActionType.PASS:
            self._do_pass(action)
        else:
            raise ValueError(f"unknown action {action}")
        return self.events[before:]

    # ---------------------------------------------------------- action handlers

    def _do_draw(self, action: Action) -> None:
        if self.phase != Phase.WAITING_DRAW or action.seat != self.current_seat:
            raise ValueError("cannot draw right now")
        p = self.players[action.seat]
        tile = self.deck.draw()
        if tile is None:
            # Wall exhausted -- exhaustive draw / "流局".
            self.phase = Phase.ROUND_OVER
            self.events.append(Event(EventType.DRAW_GAME, data={}))
            self.events.append(Event(EventType.ROUND_END, data={}))
            return
        self._place_drawn_tile(p, tile)
        self.events.append(Event(EventType.DRAW, seat=action.seat,
                                 data={"tile": p.hand.last_draw}))
        self.phase = Phase.WAITING_DISCARD

    def _place_drawn_tile(self, p: Player, tile: Tile) -> None:
        """Route a fresh tile into the hand, replacing bonuses recursively."""
        while tile.is_bonus:
            p.hand.flowers.append(tile)
            replacement = self.deck.draw_replacement()
            if replacement is None:
                p.hand.last_draw = None
                return
            tile = replacement
        p.hand.concealed.append(tile)
        p.hand.last_draw = tile

    def _do_discard(self, action: Action) -> None:
        if self.phase != Phase.WAITING_DISCARD or action.seat != self.current_seat:
            raise ValueError("cannot discard right now")
        if action.tile is None:
            raise ValueError("discard needs a tile")
        p = self.players[action.seat]
        p.hand.remove(action.tile)
        p.hand.last_draw = None
        self.last_discard = action.tile
        self.last_discarder = action.seat
        self.discards[action.seat].append(action.tile)
        self.events.append(Event(EventType.DISCARD, seat=action.seat,
                                 data={"tile": action.tile}))

        # Open the call window.
        calls = self._collect_pending_calls(action.tile, action.seat)
        if calls:
            self.pending_calls = calls
            self.phase = Phase.WAITING_CALLS
        else:
            self._advance_to_next_turn()

    def _collect_pending_calls(self, discard: Tile,
                               discarder_seat: int) -> Dict[int, List[Call]]:
        """Gather legal calls from every non-discarding player."""
        out: Dict[int, List[Call]] = {}
        for i, p in enumerate(self.players):
            if i == discarder_seat:
                continue
            is_next = (i == self.next_seat(discarder_seat))
            calls = find_calls(p.hand.concealed, discard, is_next, self.gold)
            # Also offer a win-on-discard if the hand would win.
            if check_win(p.hand.concealed, p.hand.melds, discard, self.gold).is_win:
                calls.append(Call(MeldType.PUNG, [], discard))
                # sentinel: tiles_from_hand empty means "win claim"
            if calls:
                out[i] = calls
        return out

    def _do_call(self, action: Action) -> None:
        if self.phase != Phase.WAITING_CALLS:
            raise ValueError("no call window open")
        seat, discard = action.seat, self.last_discard
        if seat not in self.pending_calls:
            raise ValueError("seat has no pending call")
        if discard is None:
            raise ValueError("no discard to call")

        p = self.players[seat]
        tiles = action.tiles_from_hand or []
        meld_type = action.meld_type or MeldType.PUNG
        for t in tiles:
            p.hand.remove(t)

        meld = Meld(
            type=meld_type,
            tiles=[*tiles, discard],
            called_from_seat=self.last_discarder,
            claimed_tile=discard,
        )
        p.hand.melds.append(meld)
        p.hand.just_called = True
        # Remove the discard from the pile (it's now the caller's).
        self.discards[self.last_discarder].pop()
        self.events.append(Event(EventType.CALL, seat=seat,
                                 data={"meld": meld}))

        # Reset call window.  Caller becomes the current seat.
        self.current_seat = seat
        self.last_discard = None
        self.pending_calls = {}

        if meld_type == MeldType.KONG_EXPOSED:
            # Caller draws a replacement then may discard.
            replacement = self.deck.draw_replacement()
            if replacement is not None:
                self._place_drawn_tile(p, replacement)
                self.events.append(Event(EventType.DRAW, seat=seat,
                                         data={"tile": p.hand.last_draw,
                                               "replacement": True}))
        self.phase = Phase.WAITING_DISCARD

    def _do_kong_concealed(self, action: Action) -> None:
        if self.phase != Phase.WAITING_DISCARD or action.seat != self.current_seat:
            raise ValueError("cannot declare concealed kong now")
        if action.tile is None:
            raise ValueError("kong needs a tile")
        p = self.players[action.seat]
        for _ in range(4):
            p.hand.remove(action.tile)
        p.hand.melds.append(Meld(
            type=MeldType.KONG_CONCEALED,
            tiles=[action.tile] * 4,
        ))
        self.events.append(Event(EventType.KONG, seat=action.seat,
                                 data={"tile": action.tile, "concealed": True}))
        replacement = self.deck.draw_replacement()
        if replacement is not None:
            self._place_drawn_tile(p, replacement)
            self.events.append(Event(EventType.DRAW, seat=action.seat,
                                     data={"tile": p.hand.last_draw,
                                           "replacement": True}))

    def _do_kong_promoted(self, action: Action) -> None:
        if self.phase != Phase.WAITING_DISCARD or action.seat != self.current_seat:
            raise ValueError("cannot promote kong now")
        if action.tile is None:
            raise ValueError("kong needs a tile")
        p = self.players[action.seat]
        for m in p.hand.melds:
            if m.type == MeldType.PUNG and m.tiles[0] == action.tile:
                p.hand.remove(action.tile)
                m.type = MeldType.KONG_PROMOTED
                m.tiles.append(action.tile)
                break
        else:
            raise ValueError("no matching pung to promote")
        self.events.append(Event(EventType.KONG, seat=action.seat,
                                 data={"tile": action.tile, "promoted": True}))
        replacement = self.deck.draw_replacement()
        if replacement is not None:
            self._place_drawn_tile(p, replacement)
            self.events.append(Event(EventType.DRAW, seat=action.seat,
                                     data={"tile": p.hand.last_draw,
                                           "replacement": True}))

    def _do_win(self, action: Action) -> None:
        seat = action.seat
        p = self.players[seat]
        self_draw = (self.phase == Phase.WAITING_DISCARD
                     and seat == self.current_seat)
        win_tile = p.hand.last_draw if self_draw else self.last_discard
        concealed_for_check = list(p.hand.concealed)
        if self_draw and win_tile is not None and win_tile in concealed_for_check:
            concealed_for_check.remove(win_tile)

        w = check_win(concealed_for_check, p.hand.melds, win_tile, self.gold)
        if not w.is_win:
            raise ValueError(f"not a winning hand: {w.reason}")

        # On discard wins, add the tile to hand now.
        if not self_draw and win_tile is not None:
            p.hand.concealed.append(win_tile)

        breakdown = score_hand(
            winner=p.hand, win=w, gold=self.gold,
            dealer_streak=self.dealer_streak if seat == self.dealer_seat else 0,
            self_draw=self_draw,
        )

        # Apply points.
        self.winning_player = seat
        self.winning_breakdown = breakdown
        if self_draw:
            for i, other in enumerate(self.players):
                if i != seat:
                    other.score -= breakdown.payout_each
                    p.score += breakdown.payout_each
        else:
            discarder = self.last_discarder
            if discarder is not None:
                self.players[discarder].score -= breakdown.payout_each
                p.score += breakdown.payout_each

        self.events.append(Event(EventType.WIN, seat=seat,
                                 data={"win": w,
                                       "breakdown": breakdown,
                                       "self_draw": self_draw}))
        self.events.append(Event(EventType.ROUND_END,
                                 data={"winner": seat}))
        self.phase = Phase.ROUND_OVER

        # Dealer streak tracking.
        if seat == self.dealer_seat:
            self.dealer_streak += 1
        else:
            self.dealer_streak = 0
            self.dealer_seat = self.next_seat(self.dealer_seat)

    def _do_pass(self, action: Action) -> None:
        if self.phase != Phase.WAITING_CALLS:
            return
        if action.seat in self.pending_calls:
            del self.pending_calls[action.seat]
        if not self.pending_calls:
            # Everyone passed; advance turn.
            self._advance_to_next_turn()

    def _advance_to_next_turn(self) -> None:
        self.current_seat = self.next_seat(self.last_discarder or self.current_seat)
        self.last_discard = None
        self.phase = Phase.WAITING_DRAW


def start_new_game(player_names: List[str], seed: Optional[int] = None) -> GameState:
    """Convenience factory mirroring GameState.new_game."""
    return GameState.new_game(player_names, seed=seed)
