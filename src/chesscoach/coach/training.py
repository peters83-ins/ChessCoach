"""Reusable state machine for short, forgiving chess exercises."""

from dataclasses import dataclass

import chess

from chesscoach.chess.game import Game
from chesscoach.coach.models import PracticeItem


@dataclass(frozen=True)
class TrainingAttempt:
    """The verified result of one learner move."""

    correct: bool
    completed: bool
    mistake: bool
    expected: str
    feedback: str
    rollback_fen: str
    forced_reply: str | None
    decision_index: int


class TrainingSession:
    """Advance a learner through a line while preserving completed decisions."""

    def __init__(self, item: PracticeItem) -> None:
        if not item.solution:
            raise ValueError("A training item must contain at least one solution move.")
        self.item = item
        self.game = Game(item.fen)
        self.solution_index = 0
        self._checkpoint_fen = item.fen
        self._active_solution = item.solution

    @property
    def completed(self) -> bool:
        return self.solution_index >= len(self._active_solution)

    @property
    def decision_index(self) -> int:
        return self.solution_index // 2

    @property
    def remaining_solution(self) -> tuple[str, ...]:
        return self._active_solution[self.solution_index :]

    def attempt(self, move: chess.Move) -> TrainingAttempt:
        """Process a move, whether the board already applied it or not."""
        if self.completed:
            raise ValueError("This training session is already complete.")
        if not self._move_is_applied(move):
            if not self.game.attempt_move(move):
                raise ValueError("The attempted move is illegal in the training position.")
        expected = self._active_solution[self.solution_index]
        accepted = move.uci() in self._accepted_moves(self.solution_index)
        if not accepted:
            self.game = Game(self._checkpoint_fen)
            return TrainingAttempt(
                False,
                False,
                True,
                expected,
                "Mistake. Try this decision again from the previous position.",
                self._checkpoint_fen,
                None,
                self.decision_index,
            )

        alternative_line = self._alternative_line(move)
        if alternative_line is not None:
            self._active_solution = self._active_solution[: self.solution_index] + alternative_line
        self.solution_index += 1
        forced_reply = None
        if self.solution_index < len(self._active_solution):
            reply = chess.Move.from_uci(self._active_solution[self.solution_index])
            if reply not in self.game.position.legal_moves:
                raise ValueError("The verified training reply is illegal in the current position.")
            self.game.attempt_move(reply)
            forced_reply = reply.uci()
            self.solution_index += 1
        self._checkpoint_fen = self.game.fen
        return TrainingAttempt(
            True,
            self.completed,
            False,
            expected,
            "Correct so far. Continue the idea after the engine reply.",
            self._checkpoint_fen,
            forced_reply,
            self.decision_index,
        )

    def _move_is_applied(self, move: chess.Move) -> bool:
        stack = self.game.position.move_stack
        return bool(stack and stack[-1] == move)

    def _alternative_line(self, move: chess.Move) -> tuple[str, ...] | None:
        for line in self.item.alternative_lines:
            if line and line[0] == move.uci():
                return line
        return None

    def _accepted_moves(self, index: int) -> tuple[str, ...]:
        if index >= len(self._active_solution):
            return ()
        accepted = (self._active_solution[index],)
        alternatives = (
            self.item.alternative_lines[index] if index < len(self.item.alternative_lines) else ()
        )
        if index == 0:
            alternatives += self.item.alternatives
        return accepted + alternatives
