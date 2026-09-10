"""Bounded local UCI searches. Call blocking methods outside the GUI thread."""

import subprocess
import sys
from collections.abc import Sequence
from typing import cast

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

    def _protocol(self) -> chess.engine.UciProtocol:
        """Return the concrete UCI protocol used by the local engine."""
        return cast(chess.engine.UciProtocol, self._engine.protocol)

    @property
    def signature(self) -> str:
        return str(self._protocol().id.get("name", "Stockfish"))

    def configure_difficulty(self, elo: int) -> int:
        """Return the practice label, or the native target clamped to the UCI range."""
        options = self._protocol().options
        option = options.get("UCI_Elo")
        if option is None or "UCI_LimitStrength" not in options:
            raise ValueError("This engine does not support Stockfish Elo difficulty settings.")
        actual = max(option.min or elo, min(elo, option.max or elo))
        self.practice_level = elo if elo in TEMPERATURES else None
        # Apply only the requested options. python-chess 1.11 can otherwise
        # replay its complete target option map, which may block with Stockfish 19.
        protocol = self._protocol()
        protocol._setoption("UCI_LimitStrength", True)
        protocol._setoption("UCI_Elo", actual)
        protocol.target_config["UCI_LimitStrength"] = True
        protocol.target_config["UCI_Elo"] = actual
        # The engine already started with the remaining defaults; mirror them in
        # python-chess state so future searches do not replay a full configure.
        protocol.config.update(protocol.target_config)
        protocol._isready()
        return elo if self.practice_level is not None else actual

    def play(self, position: chess.Board) -> chess.Move:
        if self.practice_level is not None:
            analysis = self.analyze(
                position,
                limit=chess.engine.Limit(time=0.3, nodes=12_000),
                multipv=min(position.legal_moves.count(), 12),
            )
            move = practice_move(analysis, position.turn, self.practice_level)
            if move not in position.legal_moves:
                raise ValueError("Stockfish returned an illegal practice move.")
            return move
        self._protocol()._isready()
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
        # Analyse using the current profile. Passing an options mapping to
        # python-chess replays its full target configuration, which can block
        # with Stockfish 19 under python-chess 1.11.
        self._protocol()._isready()
        information = self._engine.analyse(position, limit, multipv=multipv, root_moves=root_moves)
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
        """Stop the UCI process and release its transport.

        A transport-only close can leave Stockfish alive on Linux. Synchronizing
        first and sending ``quit`` keeps worker shutdown deterministic; the
        transport close remains a fallback for crashed engines.
        """
        try:
            self._protocol()._isready()
            self._engine.quit()
        except Exception:
            self._engine.close()
