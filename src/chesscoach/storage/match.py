"""Match metadata and timestamp tracking, separate from chess rules."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

import chess

from chesscoach.chess.game import Game
from chesscoach.storage.database import GameData, GameDatabase


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class BotMatch:
    game: Game
    player_color: chess.Color
    elo: int
    id: str = field(default_factory=lambda: str(uuid4()))
    started_at: str = field(default_factory=utc_now)
    ended_at: str | None = None
    move_timestamps: list[str] = field(default_factory=list)

    def record_position(self) -> None:
        count = len(self.game.history())
        del self.move_timestamps[count:]
        self.move_timestamps.extend(utc_now() for _ in range(count - len(self.move_timestamps)))
        if self.game.status().game_over:
            self.ended_at = self.ended_at or utc_now()
        else:
            self.ended_at = None

    def save(self, database: GameDatabase) -> str:
        self.record_position()
        return database.save_game(
            GameData.from_game(
                self.game,
                match_id=self.id,
                started_at=self.started_at,
                saved_at=utc_now(),
                ended_at=self.ended_at,
                player_color=self.player_color,
                bot_elo=self.elo,
                move_timestamps=tuple(self.move_timestamps),
            )
        )
