import chess
import pytest

from chesscoach.chess.pgn import parse_pgn
from chesscoach.chess.review import ReviewSession
from chesscoach.storage.database import GameData


def review() -> ReviewSession:
    game = parse_pgn("1. e4 e5 2. Nf3 *")
    return ReviewSession(
        GameData.from_game(
            game,
            match_id="review",
            started_at="t0",
            saved_at="t4",
            ended_at=None,
            player_color=chess.WHITE,
            bot_elo=1000,
            move_timestamps=("t1", "t2", "t3"),
        )
    )


def test_review_navigation_and_comparison_positions() -> None:
    session = review()
    assert session.total == 3
    assert session.game_at(0).fen == chess.STARTING_FEN
    assert [move.san for move in session.game_at(2).history()] == ["e4", "e5"]
    move, played = session.played_at(2)
    assert move.uci() == "e7e5"
    assert played.san == "e5"
    assert session.analysis_position(2).fen() == session.data.fens[1]
    assert session.played_at(0) is None
    assert session.analysis_position(0) is None


def test_review_games_are_copies_and_bounds_are_checked() -> None:
    session = review()
    game = session.game_at(1)
    assert game.attempt_move(chess.Move.from_uci("e7e5"))
    assert len(session.game_at(1).history()) == 1
    with pytest.raises(IndexError):
        session.game_at(4)
    with pytest.raises(IndexError):
        session.played_at(-1)
    with pytest.raises(IndexError):
        session.analysis_position(4)
