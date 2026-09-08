"""Shared result types and interface for local engine analysis."""

from dataclasses import dataclass
from typing import Protocol

import chess
import chess.engine


@dataclass(frozen=True)
class CandidateLine:
    """Engine score always uses White's perspective; PV contains legal engine moves."""

    score: chess.engine.PovScore
    moves: tuple[chess.Move, ...]
    depth: int


@dataclass(frozen=True)
class PositionAnalysis:
    fen: str
    candidates: tuple[CandidateLine, ...]

    @property
    def best_move(self) -> chess.Move | None:
        if not self.candidates or not self.candidates[0].moves:
            return None
        return self.candidates[0].moves[0]


class EngineService(Protocol):
    """Implementations use Settings.stockfish_path and own their subprocess lifetime.

    Analyze board snapshots (including history) off the GUI thread. Game-wide
    review can call this interface for each position; never ask an LLM for scores.
    """

    def analyze(
        self, position: chess.Board, *, limit: chess.engine.Limit, multipv: int = 1
    ) -> PositionAnalysis: ...

    def close(self) -> None: ...
