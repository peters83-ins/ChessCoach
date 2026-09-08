import json
import sqlite3
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
    path = tmp_path / "nested" / "games.sqlite3"
    database = GameDatabase(path)
    assert database.save_game(data) == "match-1"
    database.save_game(data)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM games").fetchone()[0] == 1
        record = connection.execute("SELECT data_json FROM games").fetchone()[0]
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
