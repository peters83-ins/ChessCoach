"""Required real subprocess tests for an installed Stockfish executable."""

import os
import time
from pathlib import Path

import chess
import chess.engine
import pytest
from PySide6.QtWidgets import QApplication

from chesscoach.engine.discovery import discover_engine
from chesscoach.engine.stockfish import Stockfish
from chesscoach.engine.worker import EngineRunner
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow


def engine_path() -> str:
    path = (
        os.getenv("CHESSCOACH_TEST_STOCKFISH", "").strip()
        or os.getenv("STOCKFISH_PATH", "").strip()
        or discover_engine()
    )
    if not path:
        pytest.fail(
            "Real Stockfish tests require an executable. Set "
            "CHESSCOACH_TEST_STOCKFISH or STOCKFISH_PATH, or install Stockfish "
            "in the app engine directory.",
            pytrace=False,
        )
    return path


pytestmark = pytest.mark.real_stockfish


def test_real_engine_analysis_move_and_cleanup() -> None:
    engine = Stockfish(engine_path())
    try:
        assert engine.configure_difficulty(1400) >= 1400
        board = chess.Board()
        result = engine.analyze(board, limit=chess.engine.Limit(time=0.1), multipv=2)
        assert len(result.candidates) == 2
        assert result.best_move in board.legal_moves
        assert result.candidates[0].score.white().score() is not None
        assert engine.play(board) in board.legal_moves
    finally:
        engine.close()
    assert engine._engine.returncode.result(timeout=3) is not None


def test_real_worker_and_cancellation(app: QApplication) -> None:
    path = engine_path()
    runner = EngineRunner()
    results, errors = [], []
    runner.result.connect(results.append)
    runner.error.connect(errors.append)
    runner.search(chess.Board(), path, 1800, True)
    deadline = time.monotonic() + 8
    while not results and not errors and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    try:
        assert not errors
        assert results and results[0].move in chess.Board().legal_moves
        results.clear()
        runner.search(chess.Board(), path, 1800, True)
        runner.cancel()
    finally:
        runner.shutdown()
    app.processEvents()
    assert not results
    assert all(not worker.isRunning() for worker in runner.workers)


@pytest.mark.parametrize("color", [chess.WHITE, chess.BLACK])
@pytest.mark.parametrize("level", [800, 1000, 1200])
def test_real_window_beginner_opponent(
    app: QApplication,
    tmp_path: Path,
    color: chess.Color,
    level: int,
) -> None:
    path = engine_path()
    window = MainWindow(database=GameDatabase(tmp_path / "match.sqlite3"))
    window.setup.engine_path.setText(path)
    window.setup.color.setCurrentIndex(0 if color else 1)
    window.setup.difficulty.setCurrentIndex(window.setup.difficulty.findData(level))
    window.show()
    window.start_match()
    if color == chess.WHITE:
        window.board.select_square(chess.E2)
        window.board.select_square(chess.E4)
    try:
        target = 2 if color else 1
        deadline = time.monotonic() + 8
        while len(window.game.history()) < target and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert len(window.game.history()) == target
        assert window.game.turn == color
        assert window.match.elo == level
        assert window.board.input_allowed
        assert window.match.move_timestamps
    finally:
        window.close()
    assert window.database.path.exists()
