"""One transactional, idempotent save API; no Qt or engine dependency."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

import chess

from chesscoach.chess.game import Game
from chesscoach.chess.pgn import export_pgn


@dataclass(frozen=True)
class GameData:
    id: str
    started_at: str
    saved_at: str
    ended_at: str | None
    player_color: str
    bot_elo: int
    result: str
    pgn: str
    moves: tuple[str, ...]
    san: tuple[str, ...]
    fens: tuple[str, ...]
    move_timestamps: tuple[str, ...]

    @classmethod
    def from_game(
        cls,
        game: Game,
        *,
        match_id: str,
        started_at: str,
        saved_at: str,
        ended_at: str | None,
        player_color: chess.Color,
        bot_elo: int,
        move_timestamps: tuple[str, ...],
    ) -> "GameData":
        position = game.position
        board = position.root()
        fens = [board.fen()]
        for move in position.move_stack:
            board.push(move)
            fens.append(board.fen())
        if len(move_timestamps) != len(position.move_stack):
            raise ValueError("Each move must have a timestamp.")
        return cls(
            match_id,
            started_at,
            saved_at,
            ended_at,
            "white" if player_color else "black",
            bot_elo,
            game.status().result,
            export_pgn(game),
            tuple(move.uci() for move in position.move_stack),
            tuple(move.san for move in game.history()),
            tuple(fens),
            move_timestamps,
        )


class GameDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save_game(self, game_data: GameData) -> str:
        """Insert/update one match atomically; repeated Save clicks never duplicate it."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=2.0)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS games ("
                "id TEXT PRIMARY KEY, started_at TEXT NOT NULL, saved_at TEXT NOT NULL, "
                "ended_at TEXT, player_color TEXT NOT NULL, bot_elo INTEGER NOT NULL, "
                "result TEXT NOT NULL, pgn TEXT NOT NULL, data_json TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET saved_at=excluded.saved_at, "
                "ended_at=excluded.ended_at, result=excluded.result, "
                "bot_elo=excluded.bot_elo, pgn=excluded.pgn, data_json=excluded.data_json",
                (
                    game_data.id,
                    game_data.started_at,
                    game_data.saved_at,
                    game_data.ended_at,
                    game_data.player_color,
                    game_data.bot_elo,
                    game_data.result,
                    game_data.pgn,
                    json.dumps(asdict(game_data)),
                ),
            )
        return game_data.id
