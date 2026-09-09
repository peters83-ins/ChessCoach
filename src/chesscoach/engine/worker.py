"""Qt bridge: cancellable engine searches with stale-result rejection."""

import logging
from dataclasses import dataclass
from threading import Event

import chess
import chess.engine
from PySide6.QtCore import QObject, QThread, Signal, Slot

from chesscoach.engine.analysis import PositionAnalysis
from chesscoach.engine.stockfish import Stockfish


@dataclass(frozen=True)
class SearchResult:
    analysis: PositionAnalysis
    move: chess.Move | None
    actual_elo: int
    engine_signature: str = "Stockfish"


class EngineWorker(QThread):
    result = Signal(int, object)
    error = Signal(int, str)

    def __init__(
        self,
        generation: int,
        position: chess.Board,
        path: str,
        elo: int,
        play: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.generation = generation
        self.position = position.copy()
        self.path, self.elo, self.play_move = path, elo, play
        self.cancelled = Event()
        self.engine: Stockfish | None = None

    def cancel(self) -> None:
        self.cancelled.set()
        if self.engine is not None:
            self.engine.close()

    def run(self) -> None:
        try:
            if self.cancelled.is_set():
                return
            self.engine = Stockfish(self.path)
            if self.cancelled.is_set():
                return
            actual = self.engine.configure_difficulty(self.elo)
            analysis = self.engine.analyze(self.position, limit=chess.engine.Limit(time=0.2))
            if self.cancelled.is_set():
                return
            move = self.engine.play(self.position) if self.play_move else None
            if not self.cancelled.is_set():
                self.result.emit(
                    self.generation,
                    SearchResult(analysis, move, actual, self.engine.signature),
                )
        except Exception as error:
            if not self.cancelled.is_set():
                logging.getLogger(__name__).exception("Stockfish search failed")
                self.error.emit(
                    self.generation, f"Stockfish: {error}. Check the executable, then Retry."
                )
        finally:
            if self.engine is not None:
                self.engine.close()


class EngineRunner(QObject):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.generation = 0
        self.workers: list[EngineWorker] = []

    def search(self, position: chess.Board, path: str, elo: int, play: bool) -> None:
        self.cancel()
        worker = EngineWorker(self.generation, position, path, elo, play, self)
        worker.result.connect(self._result)
        worker.error.connect(self._error)
        worker.finished.connect(self._finished)
        self.workers.append(worker)
        worker.start()

    @Slot()
    def _finished(self) -> None:
        worker = self.sender()
        if isinstance(worker, EngineWorker) and worker in self.workers:
            self.workers.remove(worker)
            worker.deleteLater()

    @Slot(int, object)
    def _result(self, generation: int, result: SearchResult) -> None:
        if generation == self.generation:
            self.result.emit(result)

    @Slot(int, str)
    def _error(self, generation: int, error: str) -> None:
        if generation == self.generation:
            self.error.emit(error)

    def cancel(self) -> None:
        self.generation += 1
        for worker in self.workers:
            worker.cancel()

    def shutdown(self) -> None:
        self.cancel()
        for worker in self.workers:
            worker.wait()  # Searches are cancelled; UCI startup is bounded by its timeout.
