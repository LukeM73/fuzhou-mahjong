"""
JSON protocol shared by server + client.

Design:
  * The SERVER is authoritative: it holds the GameState, applies actions, and
    broadcasts a censored "view" to each seated client on every change.
  * CLIENTS send only Action messages.  They never advance state locally.
  * Each state-update carries the seat's *own* concealed tiles explicitly and
    opaque counts for everyone else -- so nobody can cheat by reading their
    opponents' hands off the wire.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from ..game import (
    Action, ActionType, GameState, Meld, MeldType, Phase, Tile,
)


# ---------------------------------------------------------------- tile <-> dict


def tile_to_json(t: Optional[Tile]) -> Optional[str]:
    return None if t is None else t.to_id()


def tile_from_json(s: Optional[str]) -> Optional[Tile]:
    return None if s is None else Tile.from_id(s)


def meld_to_json(m: Meld) -> Dict[str, Any]:
    return {
        "type": m.type.value,
        "tiles": [tile_to_json(t) for t in m.tiles],
        "called_from": m.called_from_seat,
        "claimed": tile_to_json(m.claimed_tile),
    }


# ---------------------------------------------------------------- game state view


def build_view(gs: GameState, viewer_seat: int) -> Dict[str, Any]:
    """Per-player snapshot: includes ONLY the viewer's concealed tiles."""
    players = []
    for i, p in enumerate(gs.players):
        pd = {
            "seat": i,
            "name": p.name,
            "score": p.score,
            "is_bot": p.is_bot,
            "melds": [meld_to_json(m) for m in p.hand.melds],
            "flowers": [tile_to_json(t) for t in p.hand.flowers],
            "n_concealed": len(p.hand.concealed),
            "last_draw_visible": i == viewer_seat,
        }
        if i == viewer_seat:
            pd["concealed"] = [tile_to_json(t) for t in p.hand.concealed]
            pd["last_draw"] = tile_to_json(p.hand.last_draw)
        players.append(pd)

    pending = {}
    if viewer_seat in gs.pending_calls:
        pending[viewer_seat] = [
            {
                "type": c.type.value,
                "tiles_from_hand": [tile_to_json(t) for t in c.tiles_from_hand],
                "discard": tile_to_json(c.discard),
            }
            for c in gs.pending_calls[viewer_seat]
        ]

    return {
        "phase": gs.phase.value,
        "round": gs.round_number,
        "dealer": gs.dealer_seat,
        "dealer_streak": gs.dealer_streak,
        "current_seat": gs.current_seat,
        "last_discard": tile_to_json(gs.last_discard),
        "last_discarder": gs.last_discarder,
        "discards": [[tile_to_json(t) for t in pile] for pile in gs.discards],
        "wall_remaining": gs.deck.remaining if gs.deck else 0,
        "gold": tile_to_json(gs.deck.gold) if gs.deck else None,
        "indicator": tile_to_json(gs.deck.indicator) if gs.deck else None,
        "players": players,
        "pending_calls": pending,
        "viewer_seat": viewer_seat,
        "winner": gs.winning_player,
    }


# ---------------------------------------------------------------- action wire form


def action_to_json(a: Action) -> Dict[str, Any]:
    return {
        "type": a.type.value,
        "seat": a.seat,
        "tile": tile_to_json(a.tile),
        "meld_type": a.meld_type.value if a.meld_type else None,
        "tiles_from_hand": (
            [tile_to_json(t) for t in a.tiles_from_hand]
            if a.tiles_from_hand is not None else None
        ),
    }


def action_from_json(d: Dict[str, Any]) -> Action:
    return Action(
        type=ActionType(d["type"]),
        seat=d["seat"],
        tile=tile_from_json(d.get("tile")),
        meld_type=MeldType(d["meld_type"]) if d.get("meld_type") else None,
        tiles_from_hand=(
            [tile_from_json(t) for t in d["tiles_from_hand"]]
            if d.get("tiles_from_hand") is not None else None
        ),
    )


# ---------------------------------------------------------------- message envelope


def pack(kind: str, **body: Any) -> str:
    body["_kind"] = kind
    return json.dumps(body)


def unpack(raw: str) -> Dict[str, Any]:
    return json.loads(raw)
