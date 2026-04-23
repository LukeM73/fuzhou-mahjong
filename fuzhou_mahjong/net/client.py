"""
NetworkClient: bridges the Pygame UI to the server over WebSockets.

Design
------
* A dedicated background thread owns the asyncio event loop and the socket.
* The Pygame thread pushes Action messages through a thread-safe queue.
* Inbound server messages ("state", "lobby", "event", "chat") are deserialised
  into a lightweight ClientSnapshot object that the UI consumes on each frame.
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import websockets

from ..game import Action, Tile
from . import protocol as proto


# ---------------------------------------------------------------- snapshots


@dataclass
class ClientSnapshot:
    """Plain-data mirror of the server's per-player view."""
    phase: str = "waiting"
    round: int = 0
    dealer: int = 0
    current_seat: int = 0
    last_discard: Optional[Tile] = None
    last_discarder: Optional[int] = None
    gold: Optional[Tile] = None
    indicator: Optional[Tile] = None
    wall_remaining: int = 0
    discards: List[List[Tile]] = field(default_factory=list)
    players: List[Dict[str, Any]] = field(default_factory=list)
    pending_calls: Dict[int, List[Dict[str, Any]]] = field(default_factory=dict)
    viewer_seat: int = 0
    winner: Optional[int] = None

    @classmethod
    def from_view(cls, v: Dict[str, Any]) -> "ClientSnapshot":
        t = proto.tile_from_json
        return cls(
            phase=v["phase"],
            round=v["round"],
            dealer=v["dealer"],
            current_seat=v["current_seat"],
            last_discard=t(v["last_discard"]),
            last_discarder=v["last_discarder"],
            gold=t(v["gold"]),
            indicator=t(v["indicator"]),
            wall_remaining=v["wall_remaining"],
            discards=[[t(s) for s in pile] for pile in v["discards"]],
            players=[
                {**p,
                 "concealed": ([t(s) for s in p.get("concealed", [])]
                               if p.get("concealed") is not None else None),
                 "flowers": [t(s) for s in p.get("flowers", [])],
                 "melds": p.get("melds", []),
                 "last_draw": t(p.get("last_draw")),
                 }
                for p in v["players"]
            ],
            pending_calls=v.get("pending_calls", {}),
            viewer_seat=v["viewer_seat"],
            winner=v.get("winner"),
        )


# ---------------------------------------------------------------- network client


class NetworkClient:
    """Threaded websocket client.  Safe to share between UI + asyncio thread."""

    def __init__(self, host: str, room: str, name: str):
        self.host = host if "://" in host else f"ws://{host}"
        self.room = (room or "").upper()
        self.name = name
        self.snapshot: Optional[ClientSnapshot] = None
        self.lobby: List[Dict[str, Any]] = []
        self.seat: Optional[int] = None
        self.chat_log: List[str] = []
        self.errors: List[str] = []
        self._out_q: "queue.Queue[str]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop = False

    # ------------------------------------------------ public thread-safe API

    def connect(self) -> None:
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def send_action(self, action: Action) -> None:
        self._out_q.put(proto.pack("action", action=proto.action_to_json(action)))

    def send_ready(self) -> None:
        self._out_q.put(proto.pack("ready"))

    def send_add_bot(self) -> None:
        self._out_q.put(proto.pack("add_bot"))

    def send_chat(self, text: str) -> None:
        self._out_q.put(proto.pack("chat", text=text))

    def stop(self) -> None:
        self._stop = True
        self._out_q.put("__STOP__")

    # ------------------------------------------------ asyncio loop

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main())
        except Exception as e:
            self.errors.append(f"connection lost: {e}")

    async def _main(self) -> None:
        async with websockets.connect(self.host) as ws:
            await ws.send(proto.pack("join", name=self.name, room=self.room))

            async def outbox():
                while not self._stop:
                    item = await asyncio.get_event_loop().run_in_executor(
                        None, self._out_q.get,
                    )
                    if item == "__STOP__":
                        return
                    await ws.send(item)

            async def inbox():
                async for raw in ws:
                    self._handle_server_msg(raw)

            await asyncio.gather(inbox(), outbox())

    def _handle_server_msg(self, raw: str) -> None:
        msg = proto.unpack(raw)
        kind = msg.get("_kind")
        if kind == "state":
            self.snapshot = ClientSnapshot.from_view(msg["view"])
        elif kind == "lobby":
            self.lobby = msg.get("players", [])
        elif kind == "joined":
            self.seat = msg.get("seat")
            self.room = msg.get("room", self.room)
        elif kind == "event":
            pass   # narrative only; state snapshot covers the rest
        elif kind == "chat":
            self.chat_log.append(f"{msg.get('from','?')}: {msg.get('text','')}")
        elif kind == "error":
            self.errors.append(msg.get("message", "?"))

    # ------------------------------------------------ pygame entry

    def run_with_pygame(self) -> None:
        """Connect, wait for the lobby, then hand off to the Pygame client."""
        from ..ui.client import Client      # local to avoid a hard pygame dep
        self.connect()
        # The Pygame UI for online mode is a (small) adaptation -- it reads
        # self.snapshot on each frame rather than applying actions locally.
        # For the first cut we just print lobby status to the terminal and let
        # the user launch the UI once the game starts.
        import time
        print(f"Connecting to {self.host} ...")
        for _ in range(200):
            if self.snapshot is not None:
                break
            time.sleep(0.05)
        if self.snapshot is None and not self.lobby:
            print("no response from server yet")
        # In this cut, delegate rendering to the local Client; it receives
        # snapshots and forwards actions back via self.send_action.
        client = Client(my_seat=self.seat or 0, gs=None, network=self)
        client.run()
