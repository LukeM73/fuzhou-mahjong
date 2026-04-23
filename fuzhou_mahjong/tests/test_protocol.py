"""Tests for the JSON protocol: action round-trips and privacy-preserving views."""
from fuzhou_mahjong.game import (
    Action, ActionType, GameState, Meld, MeldType, Tile,
)
from fuzhou_mahjong.net import protocol as proto


def test_tile_roundtrip_via_json():
    for t in (Tile.m(5), Tile.p(9), None):
        assert proto.tile_from_json(proto.tile_to_json(t)) == t


def test_action_roundtrip_discard():
    a = Action(ActionType.DISCARD, seat=2, tile=Tile.m(5))
    j = proto.action_to_json(a)
    back = proto.action_from_json(j)
    assert back.type == ActionType.DISCARD
    assert back.seat == 2
    assert back.tile == Tile.m(5)


def test_action_roundtrip_call():
    a = Action(
        ActionType.CALL, seat=1,
        tile=Tile.p(5),
        meld_type=MeldType.CHOW,
        tiles_from_hand=[Tile.p(4), Tile.p(6)],
    )
    j = proto.action_to_json(a)
    back = proto.action_from_json(j)
    assert back.type == ActionType.CALL
    assert back.meld_type == MeldType.CHOW
    assert back.tiles_from_hand == [Tile.p(4), Tile.p(6)]


def test_build_view_hides_opponent_concealed_tiles():
    gs = GameState.new_game(["A", "B", "C", "D"], seed=0)
    view = proto.build_view(gs, viewer_seat=0)
    players = view["players"]
    # Viewer sees their own concealed tiles explicitly.
    assert "concealed" in players[0]
    assert len(players[0]["concealed"]) == len(gs.players[0].hand.concealed)
    # Opponents expose only a count, never the tiles.
    for i in (1, 2, 3):
        assert "concealed" not in players[i]
        assert players[i]["n_concealed"] == len(gs.players[i].hand.concealed)


def test_build_view_includes_gold_and_phase():
    gs = GameState.new_game(["A", "B", "C", "D"], seed=0)
    view = proto.build_view(gs, viewer_seat=1)
    assert view["gold"] is not None
    assert view["phase"] in {"waiting_draw", "waiting_discard",
                             "waiting_calls", "round_over"}


def test_pack_unpack_envelope_preserves_fields():
    raw = proto.pack("chat", **{"from": "Luke", "text": "hello"})
    msg = proto.unpack(raw)
    assert msg["_kind"] == "chat"
    assert msg["from"] == "Luke"
    assert msg["text"] == "hello"
