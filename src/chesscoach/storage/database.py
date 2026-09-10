"""One transactional, idempotent save API; no Qt or engine dependency."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import chess

from chesscoach.chess.game import Game
from chesscoach.chess.openings import recognize_opening
from chesscoach.chess.pgn import export_pgn, parse_pgn_games


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


@dataclass(frozen=True)
class SavedGameSummary:
    id: str
    saved_at: str
    player_color: str
    bot_elo: int
    result: str
    move_count: int
    opening: str = "Unknown opening"
    analyzed: bool = False
    practice_count: int = 0


class GameDatabase:
    def __init__(self, path: Path, legacy_path: Path | None = None) -> None:
        self.path = path
        self.legacy_path = legacy_path

    def _read_paths(self) -> tuple[Path, ...]:
        paths = [self.path]
        if self.legacy_path is not None and self.legacy_path != self.path:
            paths.append(self.legacy_path)
        return tuple(path for path in paths if path.is_file())

    @staticmethod
    def _decode(data_json: str) -> GameData:
        data = json.loads(data_json)
        for field_name in ("moves", "san", "fens", "move_timestamps"):
            data[field_name] = tuple(data[field_name])
        game_data = GameData(**data)
        game_data.validate()
        return game_data

    def list_games(self) -> tuple[SavedGameSummary, ...]:
        """List newest unique saves from current and legacy database locations."""
        games: dict[str, SavedGameSummary] = {}
        for path in reversed(self._read_paths()):
            with closing(sqlite3.connect(path, timeout=2.0)) as connection:
                table = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='games'"
                ).fetchone()
                if table is None:
                    continue
                rows = connection.execute(
                    "SELECT id, saved_at, player_color, bot_elo, result, data_json "
                    "FROM games ORDER BY saved_at DESC"
                ).fetchall()
            for game_id, saved_at, color, elo, result, data_json in rows:
                data = self._decode(data_json)
                games[game_id] = SavedGameSummary(
                    game_id,
                    saved_at,
                    color,
                    elo,
                    result,
                    len(data.moves),
                    (
                        opening.display_name
                        if (opening := recognize_opening(data.moves))
                        else "Unknown opening"
                    ),
                )
        return tuple(sorted(games.values(), key=lambda game: game.saved_at, reverse=True))

    def load_game(self, game_id: str) -> GameData | None:
        """Load and validate one record, preferring current storage."""
        for path in self._read_paths():
            with closing(sqlite3.connect(path, timeout=2.0)) as connection:
                row = connection.execute(
                    "SELECT data_json FROM games WHERE id = ?", (game_id,)
                ).fetchone()
            if row is not None:
                return self._decode(row[0])
        return None

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

    def import_pgn(
        self, text: str, *, player_color: chess.Color = chess.WHITE, bot_elo: int = 1400
    ) -> tuple[SaveResult, ...]:
        """Import every legal game in a PGN document as a new saved record."""
        try:
            games = parse_pgn_games(text)
        except ValueError as error:
            return (SaveResult(False, error=str(error)),)
        if not games:
            return (SaveResult(False, error="PGN did not contain a game."),)
        results: list[SaveResult] = []
        for game in games:
            now = datetime.now(UTC).isoformat()
            data = GameData.from_game(
                game,
                match_id=str(uuid4()),
                started_at=now,
                saved_at=now,
                ended_at=now if game.status().game_over else None,
                player_color=player_color,
                bot_elo=bot_elo,
                move_timestamps=tuple(now for _ in game.history()),
            )
            results.append(self.save_game(data))
        return tuple(results)

    def delete_game(self, game_id: str) -> bool:
        """Delete a game and its move rows from the database that contains it."""
        deleted = False
        for path in self._read_paths():
            with closing(sqlite3.connect(path, timeout=2.0)) as connection, connection:
                connection.execute("PRAGMA foreign_keys = ON")
                cursor = connection.execute("DELETE FROM games WHERE id=?", (game_id,))
                deleted = cursor.rowcount > 0 or deleted
        return deleted
