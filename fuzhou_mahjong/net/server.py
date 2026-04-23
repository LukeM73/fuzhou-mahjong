"""
WebSocket server that runs Fuzhou Mahjong rooms for friends.

Protocol (JSON text frames over ws://):

  client -> server:
    {"_kind": "join",    "name": "Luke",  "room": "ABCD"}
    {"_kind": "leave"}
    {"_kind": "ready"}
    {"_kind": "action",  "action": {...}}           # see protocol.action_to_json
    {"_kind": "chat",    "text": "..."}

  server -> client:
    {"_kind": "joined",  "seat": 2,  "room": "ABCD"}
    {"_kind": "lobby",   "players": [{"seat":0,"name":"...","ready":false}, ...]}
    {"_kind": "state",   "view": {...}}             # see protocol.build_view
    {"_kind": "event",   "events": [...]}           # narrative lines
    {"_kind": "chat",    "from": "Luke", "text": "..."}
    {"_kind": "error",   "message": "..."}

Run:
    python -m fuzhou_mahjong.net.server --host 0.0.0.0 --port 8765

The host's LAN IP (or a forwarded port / tunnel) is what friends connect to.
For quick online play across the internet, something like ngrok, Tailscale, or
Cloudflare Tunnel will expose the port.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import random
import string
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import websockets

from ..game import (
    Action, ActionType, GameState, Phase,
)
from ..game.ai import AIPlayer
from . import protocol as proto


logger = logging.getLogger("fuzhou.server")


# ---------------------------------------------------------------- room


@dataclass
class Seat:
    seat: int
    name: str = "(empty)"
    websocket: Optional[object] = None
    ready: bool = False
    is_bot: bool = False

    @property
    def filled(self) -> bool:
        return self.websocket is not None or self.is_bot


@dataclass
class Room:
    code: str
    seats: List[Seat] = field(default_factory=lambda: [Seat(i) for i in range(4)])
    gs: Optional[GameState] = None
    bots: Dict[int, AIPlayer] = field(default_factory=dict)
    started: bool = False
    bot_task: Optional[asyncio.Task] = None

    def open_seat(self) -> Optional[int]:
        for s in self.seats:
            if not s.filled:
                return s.seat
        return None

    def all_ready(self) -> bool:
        return all(s.filled and s.ready for s in self.seats)

    async def broadcast_lobby(self) -> None:
        msg = proto.pack("lobby", players=[
            {"seat": s.seat, "name": s.name, "ready": s.ready, "bot": s.is_bot}
            for s in self.seats
        ])
        await self._broadcast_raw(msg)

    async def broadcast_state(self) -> None:
        if self.gs is None:
            return
        for s in self.seats:
            if s.websocket is None:
                continue
            view = proto.build_view(self.gs, s.seat)
            try:
                await s.websocket.send(proto.pack("state", view=view))
            except Exception as e:
                logger.warning("send failed to seat %s: %s", s.seat, e)

    async def _broadcast_raw(self, msg: str) -> None:
        await asyncio.gather(*[
            s.websocket.send(msg)
            for s in self.seats if s.websocket is not None
        ], return_exceptions=True)

    # -------------------------------------------------- lifecycle

    async def start_game(self) -> None:
        names = [s.name for s in self.seats]
        self.gs = GameState.new_game(names)
        self.bots = {
            s.seat: AIPlayer(s.seat, seed=s.seat)
            for s in self.seats if s.is_bot
        }
        self.started = True
        await self.broadcast_state()
        await self._broadcast_raw(proto.pack("event", events=[
            {"type": "round_start", "dealer": self.gs.dealer_seat,
             "gold": self.gs.gold.to_id() if self.gs.gold else None},
        ]))
        # Start bot driver in the background.
        if self.bot_task is None or self.bot_task.done():
            self.bot_task = asyncio.create_task(self._drive_bots())

    async def apply_action(self, seat: int, action: Action) -> None:
        if self.gs is None:
            return
        if action.seat != seat:
            raise ValueError("seat mismatch")
        self.gs.apply(action)
        await self.broadcast_state()

    async def _drive_bots(self) -> None:
        """Background task that makes bot players take their turns."""
        while self.started and self.gs and self.gs.phase != Phase.ROUND_OVER:
            await asyncio.sleep(0.4)
            gs = self.gs
            if not gs:
                return
            if gs.phase == Phase.WAITING_DRAW and gs.current_seat in self.bots:
                gs.apply(Action(ActionType.DRAW, seat=gs.current_seat))
                await self.broadcast_state()
            elif gs.phase == Phase.WAITING_DISCARD and gs.current_seat in self.bots:
                ai = self.bots[gs.current_seat]
                gs.apply(ai.act_on_turn(gs))
                await self.broadcast_state()
            elif gs.phase == Phase.WAITING_CALLS:
                progressed = False
                for seat, calls in list(gs.pending_calls.items()):
                    if seat in self.bots:
                        gs.apply(self.bots[seat].act_on_call(gs, calls))
                        progressed = True
                        if gs.phase != Phase.WAITING_CALLS:
                            break
                if progressed:
                    await self.broadcast_state()


# ---------------------------------------------------------------- server


class Server:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.rooms: Dict[str, Room] = {}
        self.seat_of: Dict[object, (str, int)] = {}   # websocket -> (room, seat)

    def _fresh_code(self) -> str:
        while True:
            c = "".join(random.choices(string.ascii_uppercase, k=4))
            if c not in self.rooms:
                return c

    def _get_or_create_room(self, code: str) -> Room:
        code = (code or "").upper().strip() or self._fresh_code()
        if code not in self.rooms:
            self.rooms[code] = Room(code=code)
        return self.rooms[code]

    # --------------------------------------------------------- connection

    async def handler(self, websocket) -> None:
        room: Optional[Room] = None
        seat: Optional[int] = None
        try:
            async for raw in websocket:
                msg = proto.unpack(raw)
                kind = msg.get("_kind")
                if kind == "join":
                    room, seat = await self._handle_join(websocket, msg)
                elif kind == "ready":
                    await self._handle_ready(websocket)
                elif kind == "action":
                    await self._handle_action(websocket, msg)
                elif kind == "chat":
                    await self._handle_chat(websocket, msg)
                elif kind == "add_bot":
                    await self._handle_add_bot(websocket)
                elif kind == "leave":
                    break
                else:
                    await websocket.send(proto.pack(
                        "error", message=f"unknown kind {kind}",
                    ))
        except websockets.ConnectionClosed:
            pass
        finally:
            if websocket in self.seat_of:
                room_code, seat = self.seat_of.pop(websocket)
                r = self.rooms.get(room_code)
                if r:
                    r.seats[seat].websocket = None
                    r.seats[seat].ready = False
                    r.seats[seat].name = "(empty)"
                    await r.broadcast_lobby()

    # --------------------------------------------------------- handlers

    async def _handle_join(self, ws, msg) -> tuple:
        code = msg.get("room", "") or ""
        name = msg.get("name", "Anon")
        room = self._get_or_create_room(code)
        seat = room.open_seat()
        if seat is None:
            await ws.send(proto.pack("error", message="room is full"))
            return None, None
        room.seats[seat].name = name
        room.seats[seat].websocket = ws
        self.seat_of[ws] = (room.code, seat)
        await ws.send(proto.pack("joined", seat=seat, room=room.code))
        await room.broadcast_lobby()
        if room.gs is not None:
            # Mid-game join -- send current state.
            view = proto.build_view(room.gs, seat)
            await ws.send(proto.pack("state", view=view))
        return room, seat

    async def _handle_ready(self, ws) -> None:
        if ws not in self.seat_of:
            return
        code, seat = self.seat_of[ws]
        room = self.rooms[code]
        room.seats[seat].ready = True
        await room.broadcast_lobby()
        if room.all_ready() and not room.started:
            await room.start_game()

    async def _handle_add_bot(self, ws) -> None:
        if ws not in self.seat_of:
            return
        code, _ = self.seat_of[ws]
        room = self.rooms[code]
        seat = room.open_seat()
        if seat is None:
            return
        room.seats[seat].name = f"Bot-{seat}"
        room.seats[seat].is_bot = True
        room.seats[seat].ready = True
        await room.broadcast_lobby()

    async def _handle_action(self, ws, msg) -> None:
        if ws not in self.seat_of:
            return
        code, seat = self.seat_of[ws]
        room = self.rooms[code]
        try:
            action = proto.action_from_json(msg["action"])
            await room.apply_action(seat, action)
        except ValueError as e:
            await ws.send(proto.pack("error", message=str(e)))

    async def _handle_chat(self, ws, msg) -> None:
        if ws not in self.seat_of:
            return
        code, seat = self.seat_of[ws]
        room = self.rooms[code]
        name = room.seats[seat].name
        await room._broadcast_raw(proto.pack(
            "chat", **{"from": name, "text": msg.get("text", "")},
        ))

    # --------------------------------------------------------- run

    async def serve(self) -> None:
        logger.info("Listening on ws://%s:%s", self.host, self.port)
        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future()


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(prog="fuzhou_mahjong.net.server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    asyncio.run(Server(args.host, args.port).serve())


if __name__ == "__main__":
    main()
