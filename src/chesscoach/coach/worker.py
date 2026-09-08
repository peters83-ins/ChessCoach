"""Qt orchestration for cancellable full-game coaching jobs."""

from pathlib import Path
from threading import Event
from typing import cast

from PySide6.QtCore import QObject, QThread, Signal, Slot

from chesscoach.ai.client import create_client
from chesscoach.coach.feedback import OpenAIProvider, ResponsesClient
from chesscoach.coach.models import AnalysisProfile, AnalysisProgress, CoachBundle
from chesscoach.coach.pipeline import CoachPipeline
from chesscoach.coach.service import AnalysisCancelled, GameAnalysisService
from chesscoach.config import Settings
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameData


class CoachWorker(QThread):
    progress = Signal(int, object)
    result = Signal(int, object)
    error = Signal(int, str)

    def __init__(
        self,
        generation: int,
        data: GameData,
        engine_path: str,
        repository: CoachRepository,
        settings: Settings,
        profile: AnalysisProfile,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.generation = generation
        self.data = data
        self.engine_path = engine_path
        self.repository = repository
        self.settings = settings
        self.profile = profile
        self.cancelled = Event()

    def cancel(self) -> None:
        self.cancelled.set()

    def run(self) -> None:
        run_id = ""
        last = AnalysisProgress(0, len(self.data.moves), "starting")
        client = None
        try:
            run_id = self.repository.start_run(self.data.id, self.profile)

            def update(value: AnalysisProgress) -> None:
                nonlocal last
                last = value
                self.repository.update_run(run_id, "running", value.completed, value.total)
                self.progress.emit(self.generation, value)

            analysis = GameAnalysisService(cache=self.repository).analyze(
                self.data,
                self.engine_path,
                self.profile,
                cancelled=self.cancelled,
                progress=update,
            )
            self.repository.save_analysis(run_id, analysis)
            cloud = None
            if self.settings.openai_api_key and self.settings.openai_model:
                client = create_client(self.settings)
                cloud = OpenAIProvider(cast(ResponsesClient, client), self.settings.openai_model)
            update(AnalysisProgress(last.total, last.total, "feedback", last.cached))
            bundle = CoachPipeline(self.repository).build(self.data, analysis, cloud)
            if not self.cancelled.is_set():
                self.repository.update_run(run_id, "complete", last.total, last.total)
                self.result.emit(self.generation, bundle)
        except AnalysisCancelled:
            if run_id:
                self.repository.update_run(run_id, "cancelled", last.completed, last.total)
        except Exception as error:
            if run_id:
                self.repository.update_run(run_id, "failed", last.completed, last.total, str(error))
            self.error.emit(self.generation, f"Coach analysis failed: {error}")
        finally:
            if client is not None:
                client.close()


class CoachRunner(QObject):
    progress = Signal(object)
    result = Signal(object)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.generation = 0
        self.workers: list[CoachWorker] = []

    def start(
        self,
        data: GameData,
        engine_path: str,
        repository: CoachRepository,
        settings: Settings | None = None,
        profile: AnalysisProfile | None = None,
    ) -> None:
        self.cancel()
        worker = CoachWorker(
            self.generation,
            data,
            engine_path,
            repository,
            settings or Settings.from_environment(Path(".env")),
            profile or AnalysisProfile(),
            self,
        )
        worker.progress.connect(self._progress)
        worker.result.connect(self._result)
        worker.error.connect(self._error)
        worker.finished.connect(self._finished)
        self.workers.append(worker)
        worker.start()

    @Slot(int, object)
    def _progress(self, generation: int, progress: AnalysisProgress) -> None:
        if generation == self.generation:
            self.progress.emit(progress)

    @Slot(int, object)
    def _result(self, generation: int, bundle: CoachBundle) -> None:
        if generation == self.generation:
            self.result.emit(bundle)

    @Slot(int, str)
    def _error(self, generation: int, message: str) -> None:
        if generation == self.generation:
            self.error.emit(message)

    @Slot()
    def _finished(self) -> None:
        worker = self.sender()
        if isinstance(worker, CoachWorker) and worker in self.workers:
            self.workers.remove(worker)
            worker.deleteLater()

    def cancel(self) -> None:
        self.generation += 1
        for worker in self.workers:
            worker.cancel()

    def shutdown(self) -> None:
        self.cancel()
        for worker in self.workers:
            worker.wait()
