"""
End-to-end smoke test: spin up 4 AI players and drive a full game through
the state machine until round_over.  Run a handful of seeds and report
win/draw ratios.

Usage:
    python -m fuzhou_mahjong.tests.smoke_full_game
    python -m fuzhou_mahjong.tests.smoke_full_game --games 25 --seed 7
"""
from __future__ import annotations

import argparse
import sys
import time

from fuzhou_mahjong.game import (
    Action, ActionType, GameState, Phase,
)
from fuzhou_mahjong.game.ai import AIPlayer


MAX_STEPS = 2000   # safety guard


def run_game(seed: int) -> dict:
    gs = GameState.new_game(["A", "B", "C", "D"], seed=seed)
    bots = [AIPlayer(i, seed=seed + i) for i in range(4)]
    steps = 0
    while gs.phase != Phase.ROUND_OVER and steps < MAX_STEPS:
        steps += 1
        if gs.phase == Phase.WAITING_DRAW:
            gs.apply(Action(ActionType.DRAW, seat=gs.current_seat))
        elif gs.phase == Phase.WAITING_DISCARD:
            gs.apply(bots[gs.current_seat].act_on_turn(gs))
        elif gs.phase == Phase.WAITING_CALLS:
            # Resolve every pending caller in turn.
            for seat in list(gs.pending_calls.keys()):
                calls = gs.pending_calls.get(seat, [])
                if not calls:
                    continue
                gs.apply(bots[seat].act_on_call(gs, calls))
                if gs.phase != Phase.WAITING_CALLS:
                    break
        else:
            break

    return {
        "seed": seed,
        "steps": steps,
        "phase": gs.phase.value,
        "winner": gs.winning_player,
        "wall_remaining": gs.deck.remaining if gs.deck else 0,
        "gold": gs.gold.short if gs.gold else None,
        "scores": [p.score for p in gs.players],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    wins = draws = 0
    t0 = time.time()
    for i in range(args.games):
        res = run_game(args.seed + i)
        if res["winner"] is not None:
            wins += 1
        else:
            draws += 1
        if args.verbose:
            print(
                f"seed {res['seed']:>4}  "
                f"steps {res['steps']:>4}  "
                f"phase {res['phase']:<14}  "
                f"winner {res['winner']}  "
                f"gold {res['gold']}  "
                f"wall {res['wall_remaining']:>3}  "
                f"scores {res['scores']}"
            )
    dt = time.time() - t0
    print(f"\n{args.games} games  |  {wins} wins  |  {draws} draws  |  "
          f"{dt:.2f}s total  ({args.games/dt:.1f} games/sec)")
    if args.games and wins == 0:
        print("WARNING: zero wins observed -- engine may be broken.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
