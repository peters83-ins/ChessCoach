"""All chess mechanics are delegated to python-chess."""

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class PlayedMove:
    number: int
    color: chess.Color
    san: str


@dataclass(frozen=True)
class GameStatus:
    turn: chess.Color
    in_check: bool
    game_over: bool
    result: str
    message: str
    can_claim_draw: bool = False


class Game:
    """Own a standard chess game; callers receive copies of mutable board state.

    Claimable draws are explicitly claimed. Automatic draws end play immediately.
    Undo removes one ply and clears any draw claim; reset starts standard chess.
    """

    def __init__(self, fen: str = chess.STARTING_FEN) -> None:
        board = chess.Board(fen)
        if not board.is_valid():
            raise ValueError("The starting position is not a valid chess position.")
        self._board = board
        self._claimed_draw = False

    @property
    def position(self) -> chess.Board:
        return self._board.copy()

    @property
    def fen(self) -> str:
        return self._board.fen()

    @property
    def turn(self) -> chess.Color:
        return self._board.turn

    @property
    def can_undo(self) -> bool:
        return bool(self._board.move_stack) or self._claimed_draw

    def copy(self) -> "Game":
        clone = object.__new__(Game)
        clone._board = self._board.copy()
        clone._claimed_draw = self._claimed_draw
        return clone

    def piece_at(self, square: chess.Square) -> chess.Piece | None:
        return self._board.piece_at(square)

    def legal_moves_from(self, square: chess.Square) -> tuple[chess.Move, ...]:
        if self.status().game_over:
            return ()
        return tuple(move for move in self._board.legal_moves if move.from_square == square)

    def attempt_move(self, move: chess.Move) -> bool:
        if self.status().game_over or move not in self._board.legal_moves:
            return False
        self._board.push(move)
        return True

    def undo(self) -> bool:
        if self._claimed_draw:
            self._claimed_draw = False
            return True
        if not self._board.move_stack:
            return False
        self._board.pop()
        return True

    def reset(self) -> None:
        self._board.reset()
        self._claimed_draw = False

    def history(self) -> tuple[PlayedMove, ...]:
        board = self._board.root()
        history = []
        for move in self._board.move_stack:
            history.append(PlayedMove(board.fullmove_number, board.turn, board.san(move)))
            board.push(move)
        return tuple(history)

    def claim_draw(self) -> bool:
        if self.status().game_over or not self._board.can_claim_draw():
            return False
        self._claimed_draw = True
        return True

    def status(self) -> GameStatus:
        outcome = self._board.outcome()
        side = "White" if self.turn else "Black"
        if self._claimed_draw:
            message, result = "Draw claimed", "1/2-1/2"
        elif outcome:
            result = outcome.result()
            reason = outcome.termination.name.replace("_", " ").capitalize()
            if outcome.winner is None:
                message = f"Draw — {reason.lower()}"
            else:
                winner = "White" if outcome.winner else "Black"
                message = f"{reason} — {winner} wins"
        else:
            result = "*"
            message = f"{side} to move" + (" — check" if self._board.is_check() else "")
        game_over = self._claimed_draw or outcome is not None
        return GameStatus(
            turn=self.turn,
            in_check=self._board.is_check(),
            game_over=game_over,
            result=result,
            message=message,
            can_claim_draw=not game_over and self._board.can_claim_draw(),
        )
