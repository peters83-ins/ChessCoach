import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from chesscoach.chess.pgn import parse_pgn
from chesscoach.storage.database import GameData, GameDatabase


def test_save_full_game_and_retry_without_duplicates(tmp_path: Path) -> None:
    game = parse_pgn("1. f3 e5 2. g4 Qh4# 0-1")
    data = GameData.from_game(
        game,
        match_id="match-1",
        started_at="2026-09-07T12:00:00+00:00",
        saved_at="2026-09-07T12:05:00+00:00",
        ended_at="2026-09-07T12:05:00+00:00",
        player_color=True,
        bot_elo=1800,
        move_timestamps=("t1", "t2", "t3", "t4"),
    )
    games_folder = tmp_path / "games"
    path = games_folder / "games.sqlite3"
    assert not games_folder.exists()
    database = GameDatabase(path)
    result = database.save_game(data)
    assert result.success and result.game_id == "match-1" and result.error is None
    assert games_folder.is_dir()
    assert database.save_game(data).success
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM games").fetchone()[0] == 1
        record = connection.execute("SELECT data_json FROM games").fetchone()[0]
        moves = connection.execute(
            "SELECT ply, uci, san, fen_before, fen_after, played_at FROM game_moves ORDER BY ply"
        ).fetchall()
    restored = json.loads(record)
    assert restored["player_color"] == "white"
    assert restored["bot_elo"] == 1800
    assert restored["result"] == "0-1"
    assert restored["moves"] == ["f2f3", "e7e5", "g2g4", "d8h4"]
    assert restored["san"][-1] == "Qh4#"
    assert len(restored["fens"]) == 5
    assert restored["fens"][-1] == game.fen
    assert parse_pgn(restored["pgn"]).fen == game.fen
    assert restored["move_timestamps"] == ["t1", "t2", "t3", "t4"]
    assert [move[1] for move in moves] == restored["moves"]
    assert [move[2] for move in moves] == restored["san"]
    assert [move[5] for move in moves] == restored["move_timestamps"]
    assert moves[0][3] == restored["fens"][0]
    assert moves[-1][4] == restored["fens"][-1]


def test_missing_move_timestamps_rejected() -> None:
    with pytest.raises(ValueError, match="timestamp"):
        GameData.from_game(
            parse_pgn("1. e4 *"),
            match_id="id",
            started_at="t0",
            saved_at="t1",
            ended_at=None,
            player_color=False,
            bot_elo=1400,
            move_timestamps=(),
        )


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"moves": ()}, "Move list"),
        ({"move_timestamps": ("t1",)}, "equal lengths"),
        ({"player_color": ""}, "Player color"),
        ({"bot_elo": 0}, "Bot difficulty"),
        ({"bot_elo": "easy"}, "Bot difficulty"),
    ],
)
def test_incomplete_game_data_returns_failure(
    tmp_path: Path, change: dict[str, object], error: str
) -> None:
    data = GameData.from_game(
        parse_pgn("1. e4 e5 *"),
        match_id="id",
        started_at="t0",
        saved_at="t1",
        ended_at=None,
        player_color=True,
        bot_elo=1000,
        move_timestamps=("t1", "t2"),
    )
    result = GameDatabase(tmp_path / "games" / "games.sqlite3").save_game(replace(data, **change))
    assert not result.success
    assert result.game_id is None
    assert error in (result.error or "")
    assert not (tmp_path / "games").exists()
