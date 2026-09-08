"""Bounded local UCI searches. Call blocking methods outside the GUI thread."""

import subprocess
import sys
from collections.abc import Sequence

import chess
import chess.engine

from chesscoach.engine.analysis import CandidateLine, PositionAnalysis
from chesscoach.engine.practice import TEMPERATURES, practice_move

DIFFICULTIES = {
    "Beginner · ~800 practice": 800,
    "Casual · ~1000 practice": 1000,
    "Improving · ~1200 practice": 1200,
    "Club · ~1400": 1400,
    "Intermediate · ~1800": 1800,
    "Strong · ~2200": 2200,
}


class Stockfish:
    def __init__(self, path: str) -> None:
        self.practice_level: int | None = None
        if not path.strip():
            raise ValueError("Select a Stockfish executable or set STOCKFISH_PATH.")
        if sys.platform == "win32":
            self._engine = chess.engine.SimpleEngine.popen_uci(
                path, timeout=3.0, creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            self._engine = chess.engine.SimpleEngine.popen_uci(path, timeout=3.0)

    @property
    def signature(self) -> str:
        return str(self._engine.id.get("name", "Stockfish"))

    def configure_difficulty(self, elo: int) -> int:
        """Return the practice label, or the native target clamped to the UCI range."""
        option = self._engine.options.get("UCI_Elo")
        if option is None or "UCI_LimitStrength" not in self._engine.options:
            raise ValueError("This engine does not support Stockfish Elo difficulty settings.")
        actual = max(option.min or elo, min(elo, option.max or elo))
        self.practice_level = elo if elo in TEMPERATURES else None
        self._engine.configure({"UCI_LimitStrength": True, "UCI_Elo": actual})
        return elo if self.practice_level is not None else actual

    def play(self, position: chess.Board) -> chess.Move:
        if self.practice_level is not None:
            analysis = self.analyze(
                position,
                limit=chess.engine.Limit(time=0.3, nodes=12_000),
                multipv=position.legal_moves.count(),
            )
            move = practice_move(analysis, position.turn, self.practice_level)
            if move not in position.legal_moves:
                raise ValueError("Stockfish returned an illegal practice move.")
            return move
        result = self._engine.play(position, chess.engine.Limit(time=0.3))
        if result.move is None or result.move not in position.legal_moves:
            raise ValueError("Stockfish returned no legal move. Retry the engine search.")
        return result.move

    def analyze(
        self,
        position: chess.Board,
        *,
        limit: chess.engine.Limit,
        multipv: int = 1,
        root_moves: Sequence[chess.Move] | None = None,
        pv_plies: int | None = None,
    ) -> PositionAnalysis:
        if not position.is_valid():
            raise ValueError("Cannot analyze an invalid position.")
        if multipv < 1:
            raise ValueError("MultiPV must be positive.")
        if root_moves is not None and any(move not in position.legal_moves for move in root_moves):
            raise ValueError("Root analysis moves must be legal in the supplied position.")
        if pv_plies is not None and pv_plies < 1:
            raise ValueError("PV length must be positive.")
        # Analysis uses full strength even when the opponent is strength-limited.
        information = self._engine.analyse(
            position,
            limit,
            multipv=multipv,
            root_moves=root_moves,
            options={"UCI_LimitStrength": False},
        )
        candidates = []
        for info in information:
            score = info.get("score")
            if score is None:
                raise ValueError("Stockfish returned no evaluation.")
            moves = tuple(info.get("pv", []))
            if pv_plies is not None:
                moves = moves[:pv_plies]
            board = position.copy()
            for move in moves:
                if move not in board.legal_moves:
                    raise ValueError("Stockfish returned an invalid principal variation.")
                board.push(move)
            candidates.append(
                CandidateLine(
                    chess.engine.PovScore(score.white(), chess.WHITE), moves, info.get("depth", 0)
                )
            )
        if not candidates:
            raise ValueError("Stockfish returned no analysis.")
        return PositionAnalysis(position.fen(), tuple(candidates))

    def close(self) -> None:
        """Thread-safe immediate cancellation and process/transport cleanup."""
        self._engine.close()
