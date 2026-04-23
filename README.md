# Fuzhou Mahjong

A four-player online Mahjong game using the **Fuzhou (福州) Mahjong** ruleset
— the 16-tile variant from Fujian province with the Gold Tile (金 *Jin*)
wildcard mechanic.

Built in Python with Pygame for the client and a websockets-based room
server so you can play with friends across the internet.

---

## Quick start

### 1. Install

```bash
cd "Mahjong Game"
pip install -r requirements.txt
```

Requirements: Python 3.10+, Pygame 2.5+, websockets 12+, Pillow 10+.

### 2. Solo / hot-seat (no network)

```bash
python -m fuzhou_mahjong.ui.client --solo
```

This launches a local Pygame window with you in seat 0 and AI opponents in
seats 1–3.

### 3. Online with friends

On the **host** machine:

```bash
python -m fuzhou_mahjong.net.server --host 0.0.0.0 --port 8765
```

Each **player** (including the host) launches a client pointing at the
server's address and a 4-letter room code:

```bash
python -m fuzhou_mahjong.ui.client \
  --host ws://YOUR.SERVER.IP:8765 \
  --room ABCD \
  --name Luke
```

The first player creates the room (any 4-letter code; if blank the server
picks one and tells you in the lobby). Other players use the same code to
join the same table. When all four seats are filled and ready, the game
starts. Empty seats can be filled with bots from the lobby.

To play across the internet, expose port 8765 by port-forwarding, by using
[Tailscale](https://tailscale.com), [ngrok](https://ngrok.com), or
Cloudflare Tunnel.

---

## Controls

In the client window:

- Click a tile in your hand to select it; click the **Discard** button (or
  click again) to throw it.
- **Draw** appears on your turn when the wall has tiles.
- **Mahjong** appears whenever your hand can win (with the current draw or
  on a discard you can claim).
- **Kong** appears whenever you can declare a concealed kong or promote an
  existing exposed pung.
- **Pass** dismisses a call window when you don't want to claim a discard.
- **Call** offers chow / pung / kong choices when somebody discards a tile
  you can use.

Press `Esc` to quit. Drag the window to resize.

---

## Fuzhou Mahjong — rules summary

### Tiles (144 total)

- **108 numbered tiles** in three suits, 4 copies of each: Characters
  (萬 *Man*), Dots (筒 *Pin*), Bamboo (條 *Sou*), values 1–9.
- **28 honor tiles**: 4 winds × 4 copies, 3 dragons × 4 copies.
- **8 flower/season bonus tiles** (one of each flower, one of each season).

In Fuzhou play, only the 108 numbered tiles form melds. Honors and
flowers/seasons are **bonus tiles** — when drawn, they're set aside in your
flower rack and you immediately draw a replacement.

### Hand size

- Each player ends with **16 concealed tiles** in hand.
- The dealer starts with 17 (so they can discard first).
- A winning hand is **5 sets + 1 pair = 17 logical tiles**.

### The Gold Tile (金 Jin)

After the deal, one tile is flipped from the back of the wall as the
**indicator**. The next-in-sequence tile of that suit becomes the **Gold**:
all four copies of that tile-value are universal wildcards that can fill
any pair, pung, or chow.

A Gold tile that gets discarded **cannot be claimed** by anyone — it goes
straight to the discard pile.

### Sets

- **Chow** (顺) — three consecutive tiles of the same suit (e.g. 3-4-5
  Bamboo). May only be called by the player immediately *downstream* of the
  discarder.
- **Pung** (碰) — three identical tiles. Can be called by any player.
- **Kong** (杠) — four identical tiles. Three flavours:
  - **Exposed kong**: three from hand + claimed discard.
  - **Concealed kong**: all four from hand, declared by the holder.
  - **Promoted kong**: a previously exposed pung upgraded with the 4th tile.
  - All kong holders draw a **replacement tile** from the back of the wall.

### Special hands

| Hand | Trigger | Bonus |
|---|---|---|
| **All Sequences** (Ping Hu) | every set is a chow | +15 |
| **All Triplets** | every set is a pung/kong | +20 |
| **All Concealed** | no exposed melds | +10 |
| **One Suit** | winning hand uses a single numbered suit | +20 |
| **Three Golden Tiles** | drawing the third Gold (instant win) | +40 |
| **Golden Dragon** | three Golds form a pung in the winning hand | +30 |
| **Golden Pair** | two Golds form the pair | +10 |
| **Seven Flowers** | 7 or more bonus tiles in your rack | +20 |
| **Full Flower Set** | all four of one bonus group (winds, dragons, etc.) | +10 |

### Scoring

```
subtotal = (Base + FlowerFan + GoldFan + DealerStreak + KongFan) × 2
payout   = subtotal + SpecialHandBonus
```

Where:

- **Base** = 5
- **FlowerFan** = 1 per flower in your rack (+ 6 per full set)
- **GoldFan** = 1 per Gold tile in your final hand
- **DealerStreak** = the dealer's consecutive-win count
- **KongFan** = 1 per exposed kong + 2 per concealed kong (winner only)

**Self-draw wins** are paid by all three losers; **discard wins** are paid
only by the discarder.

---

## Architecture

```
fuzhou_mahjong/
├── game/        Pure-Python rules engine
│   ├── tiles.py        Tile model + Gold-from-indicator
│   ├── deck.py         Shuffle + deal (with bonus replacement)
│   ├── hand.py         Concealed tiles + melds + flower rack
│   ├── melds.py        Chow/pung/kong + call detection
│   ├── win.py          Backtracking decomposer + waits
│   ├── score.py        Fuzhou scoring formula + specials
│   ├── state.py        Game state machine
│   └── ai.py           Simple shanten-based AI for seat-fills
├── ui/          Pygame client + tile rendering
│   ├── client.py       Pygame UI (works solo or networked)
│   └── render_tiles.py PIL tile artwork generator
├── net/         WebSocket server + client
│   ├── server.py       Authoritative room server
│   ├── client.py       Threaded client → bridges asyncio + Pygame
│   └── protocol.py     JSON wire format (privacy-preserving views)
├── tests/       Pytest suite + smoke test
│   ├── test_tiles.py   ┐
│   ├── test_deck.py    │
│   ├── test_melds.py   ├ unit tests
│   ├── test_win.py     │
│   ├── test_score.py   │
│   ├── test_protocol.py┘
│   ├── run_tests.py    Zero-dependency runner (when pytest unavailable)
│   └── smoke_full_game.py  End-to-end AI vs AI smoke test
├── assets/tiles/  Auto-generated tile PNGs (96 × 128)
└── requirements.txt
```

### Why server-authoritative?

The server holds the canonical `GameState` and broadcasts a **per-player
censored view** to each seated client. Each view contains only the viewer's
own concealed tiles; opponents see only counts. This means clients can't
cheat by reading the wire — only the server knows everyone's full hand.

---

## Running tests

```bash
# With pytest (recommended)
pytest fuzhou_mahjong/tests

# Without pytest (built-in fallback runner)
python -m fuzhou_mahjong.tests.run_tests

# End-to-end smoke test (4 AIs play full games)
python -m fuzhou_mahjong.tests.smoke_full_game --games 30 --verbose
```

55 unit tests cover the tile model, dealing, calls, win detection (with
all the Gold-wildcard edge cases), and the scoring formula. The smoke test
plays full hands AI vs AI and reports win/draw rates.

---

## Tweaking

Tile artwork is generated on first run. To regenerate (e.g. after editing
colours in `ui/render_tiles.py`), delete `fuzhou_mahjong/assets/tiles/` and
run the client once.

Special-hand point values live in `game/score.py` →
`SPECIAL_HAND_POINTS`. The base scoring formula is in `score_hand()`.

---

## Credits

Rules adapted from the [Mahjong Pros guide to Fuzhou
Mahjong](https://mahjongpros.com/blogs/how-to-play/beginners-guide-to-fuzhou-mahjong).
Built with Pygame, Pillow, and websockets.
