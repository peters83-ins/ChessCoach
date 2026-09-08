"""Precomputed immutable navigation through one validated saved game."""

from dataclasses import dataclass, field

import chess

from chesscoach.chess.game import Game, PlayedMove
from chesscoach.storage.database import GameData


@dataclass
class ReviewSession:
    data: GameData
    index: int = 0
    _games: tuple[Game, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.data.validate()
        game = Game(self.data.fens[0])
        games = [game.copy()]
        for uci in self.data.moves:
            if not game.attempt_move(chess.Move.from_uci(uci)):
                raise ValueError("Saved move history is invalid.")
            games.append(game.copy())
        self._games = tuple(games)

    @property
    def total(self) -> int:
        return len(self.data.moves)

    @property
    def history(self) -> tuple[PlayedMove, ...]:
        return self._games[-1].history()

    def game_at(self, index: int) -> Game:
        self._validate_index(index)
        self.index = index
        return self._games[index].copy()

    def played_at(self, index: int) -> tuple[chess.Move, PlayedMove] | None:
        self._validate_index(index)
        if index == 0:
            return None
        return chess.Move.from_uci(self.data.moves[index - 1]), self.history[index - 1]

    def analysis_position(self, index: int) -> chess.Board | None:
        self._validate_index(index)
        return self._games[index - 1].position if index > 0 else None

    def _validate_index(self, index: int) -> None:
        if not 0 <= index <= self.total:
            raise IndexError("Review index is out of range.")
