from threading import Event

import chess
import pytest
from PySide6.QtWidgets import QApplication

from chesscoach.engine.worker import EngineRunner


def test_cancel_active_search_closes_engine(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    started, closed = Event(), Event()

    class BlockingEngine:
        def __init__(self, path: str) -> None:
            pass

        def configure_difficulty(self, elo: int) -> int:
            return elo

        def analyze(self, *args: object, **kwargs: object) -> None:
            started.set()
            assert closed.wait(2)
            raise RuntimeError("Cancelled")

        def close(self) -> None:
            closed.set()

    monkeypatch.setattr("chesscoach.engine.worker.Stockfish", BlockingEngine)
    runner = EngineRunner()
    results, errors = [], []
    runner.result.connect(results.append)
    runner.error.connect(errors.append)
    runner.search(chess.Board(), "unused", 1400, True)
    try:
        assert started.wait(1)
    finally:
        runner.shutdown()
    app.processEvents()
    assert closed.is_set()
    assert results == errors == []


def test_malformed_engine_output_reports_a_retryable_error(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    finished = Event()

    class BrokenEngine:
        signature = "Broken Stockfish"

        def __init__(self, path: str) -> None:
            pass

        def configure_difficulty(self, elo: int) -> int:
            return elo

        def analyze(self, *args: object, **kwargs: object) -> None:
            raise ValueError("Stockfish returned no evaluation")

        def close(self) -> None:
            finished.set()

    monkeypatch.setattr("chesscoach.engine.worker.Stockfish", BrokenEngine)
    runner = EngineRunner()
    errors: list[str] = []
    runner.error.connect(lambda message: (errors.append(message), finished.set()))
    runner.search(chess.Board(), "unused", 1000, False)
    try:
        assert finished.wait(2)
        app.processEvents()
    finally:
        runner.shutdown()
    assert errors and "no evaluation" in errors[0]
