"""Optional real subprocess tests: set CHESSCOACH_TEST_STOCKFISH to an executable."""

import os
import time
from pathlib import Path

import chess
import chess.engine
import pytest
from PySide6.QtWidgets import QApplication

from chesscoach.engine.stockfish import Stockfish
from chesscoach.engine.worker import EngineRunner
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow

ENGINE_PATH = os.getenv("CHESSCOACH_TEST_STOCKFISH", "")
pytestmark = pytest.mark.skipif(not ENGINE_PATH, reason="CHESSCOACH_TEST_STOCKFISH is unset")


def test_real_engine_analysis_move_and_cleanup() -> None:
    engine = Stockfish(ENGINE_PATH)
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
    runner = EngineRunner()
    results, errors = [], []
    runner.result.connect(results.append)
    runner.error.connect(errors.append)
    runner.search(chess.Board(), ENGINE_PATH, 1800, True)
    deadline = time.monotonic() + 8
    while not results and not errors and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    try:
        assert not errors
        assert results and results[0].move in chess.Board().legal_moves
        results.clear()
        runner.search(chess.Board(), ENGINE_PATH, 1800, True)
        runner.cancel()
    finally:
        runner.shutdown()
    app.processEvents()
    assert not results
    assert all(not worker.isRunning() for worker in runner.workers)


def test_real_window_engine_opens_for_black(app: QApplication, tmp_path: Path) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "match.sqlite3"))
    window.setup.engine_path.setText(ENGINE_PATH)
    window.setup.color.setCurrentIndex(1)
    window.show()
    window.start_match()
    try:
        deadline = time.monotonic() + 8
        while not window.game.history() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        assert len(window.game.history()) == 1
        assert window.game.turn == chess.BLACK
        assert window.board.input_allowed
        assert window.match.move_timestamps
    finally:
        window.close()
    assert window.database.path.exists()
