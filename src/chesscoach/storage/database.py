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

    def validate(self) -> None:
        """Reject incomplete or internally inconsistent match records."""
        if not self.id or not self.started_at or not self.saved_at:
            raise ValueError("Missing game identity or timestamps.")
        if self.player_color not in {"white", "black"}:
            raise ValueError("Player color must be white or black.")
        if isinstance(self.bot_elo, bool) or not isinstance(self.bot_elo, int) or self.bot_elo <= 0:
            raise ValueError("Bot difficulty must be a positive integer.")
        move_count = len(self.moves)
        if move_count == 0:
            raise ValueError("Move list is empty.")
        if len(self.san) != move_count or len(self.move_timestamps) != move_count:
            raise ValueError("Moves, SAN, and timestamps must have equal lengths.")
        if len(self.fens) != move_count + 1:
            raise ValueError("FEN history must include the initial and every moved position.")
        if any(not timestamp for timestamp in self.move_timestamps):
            raise ValueError("Move timestamps cannot be empty.")
        board = chess.Board(self.fens[0])
        for index, uci in enumerate(self.moves):
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves or board.san(move) != self.san[index]:
                raise ValueError("Move history contains an illegal or inconsistent move.")
            board.push(move)
            if board.fen() != self.fens[index + 1]:
                raise ValueError("FEN history does not match the move list.")

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
        game_data = cls(
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
        game_data.validate()
        return game_data


@dataclass(frozen=True)
class SaveResult:
    success: bool
    game_id: str | None = None
    error: str | None = None


class GameDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save_game(self, game_data: GameData) -> SaveResult:
        """Insert/update one match atomically; repeated Save clicks never duplicate it."""
        try:
            game_data.validate()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.path, timeout=2.0)) as connection, connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS games ("
                    "id TEXT PRIMARY KEY, started_at TEXT NOT NULL, saved_at TEXT NOT NULL, "
                    "ended_at TEXT, player_color TEXT NOT NULL, bot_elo INTEGER NOT NULL, "
                    "result TEXT NOT NULL, pgn TEXT NOT NULL, data_json TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS game_moves ("
                    "game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE, "
                    "ply INTEGER NOT NULL, uci TEXT NOT NULL, san TEXT NOT NULL, "
                    "fen_before TEXT NOT NULL, fen_after TEXT NOT NULL, "
                    "played_at TEXT NOT NULL, PRIMARY KEY (game_id, ply))"
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
                connection.execute("DELETE FROM game_moves WHERE game_id = ?", (game_data.id,))
                connection.executemany(
                    "INSERT INTO game_moves VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        (
                            game_data.id,
                            index + 1,
                            uci,
                            game_data.san[index],
                            game_data.fens[index],
                            game_data.fens[index + 1],
                            game_data.move_timestamps[index],
                        )
                        for index, uci in enumerate(game_data.moves)
                    ),
                )
        except (OSError, sqlite3.Error, ValueError) as error:
            return SaveResult(False, error=str(error))
        return SaveResult(True, game_id=game_data.id)
