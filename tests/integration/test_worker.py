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
