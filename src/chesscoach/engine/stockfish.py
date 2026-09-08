"""Bounded local UCI searches. Call blocking methods outside the GUI thread."""

import chess
import chess.engine

from chesscoach.engine.analysis import CandidateLine, PositionAnalysis

DIFFICULTIES = {"Club · ~1400": 1400, "Intermediate · ~1800": 1800, "Strong · ~2200": 2200}


class Stockfish:
    def __init__(self, path: str) -> None:
        if not path.strip():
            raise ValueError("Select a Stockfish executable or set STOCKFISH_PATH.")
        self._engine = chess.engine.SimpleEngine.popen_uci(path, timeout=3.0)

    def configure_difficulty(self, elo: int) -> int:
        """Return the actual target after clamping to this executable's UCI range."""
        option = self._engine.options.get("UCI_Elo")
        if option is None or "UCI_LimitStrength" not in self._engine.options:
            raise ValueError("This engine does not support Stockfish Elo difficulty settings.")
        actual = max(option.min or elo, min(elo, option.max or elo))
        self._engine.configure({"UCI_LimitStrength": True, "UCI_Elo": actual})
        return actual

    def play(self, position: chess.Board) -> chess.Move:
        result = self._engine.play(position, chess.engine.Limit(time=0.3))
        if result.move is None or result.move not in position.legal_moves:
            raise ValueError("Stockfish returned no legal move. Retry the engine search.")
        return result.move

    def analyze(
        self, position: chess.Board, *, limit: chess.engine.Limit, multipv: int = 1
    ) -> PositionAnalysis:
        if not position.is_valid():
            raise ValueError("Cannot analyze an invalid position.")
        if multipv < 1:
            raise ValueError("MultiPV must be positive.")
        # Analysis uses full strength even when the opponent is strength-limited.
        information = self._engine.analyse(
            position, limit, multipv=multipv, options={"UCI_LimitStrength": False}
        )
        candidates = []
        for info in information:
            score = info.get("score")
            if score is None:
                raise ValueError("Stockfish returned no evaluation.")
            moves = tuple(info.get("pv", []))
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
