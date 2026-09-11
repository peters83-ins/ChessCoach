import sqlite3
from contextlib import closing
from pathlib import Path
from threading import Event

import chess
import pytest
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from chesscoach.chess.pgn import parse_pgn
from chesscoach.coach.models import (
    AnalysisProfile,
    AnalysisProgress,
    EngineScore,
    Evidence,
    GameAnalysis,
    GamePhase,
    MoveAnalysis,
    MoveClassification,
    PhaseSummary,
)
from chesscoach.coach.service import AnalysisCancelled
from chesscoach.coach.worker import CoachRunner
from chesscoach.config import Settings
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameData


def game_data() -> GameData:
    return GameData.from_game(
        parse_pgn("1. f3 *"),
        match_id="worker-game",
        started_at="start",
        saved_at="saved",
        ended_at=None,
        player_color=chess.WHITE,
        bot_elo=1000,
        move_timestamps=("move",),
    )


def analysis() -> GameAnalysis:
    move = MoveAnalysis(
        1,
        chess.STARTING_FEN,
        "white",
        "f2f3",
        "f3",
        "e2e4",
        "e4",
        EngineScore(centipawns=50),
        EngineScore(centipawns=-100),
        12,
        82,
        MoveClassification.MISTAKE,
        GamePhase.OPENING,
        ("e2e4", "e7e5"),
        ("f2f3", "e7e5"),
        14,
        (Evidence("fact", "calculation", "The best continuation was missed."),),
        ("calculation",),
        True,
    )
    return GameAnalysis(
        "worker-game",
        AnalysisProfile(engine_signature="Fake"),
        (move,),
        (1,),
        82,
        (PhaseSummary(GamePhase.OPENING, 82, 1, 1),),
    )


def test_coach_runner_persists_completed_background_job(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = analysis()

    class FakeService:
        def __init__(self, cache=None) -> None:
            pass

        def analyze(self, *args, progress, **kwargs):
            progress(AnalysisProgress(1, 1, "quick"))
            return expected

    monkeypatch.setattr("chesscoach.coach.worker.GameAnalysisService", FakeService)
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    runner = CoachRunner()
    progress = QSignalSpy(runner.progress)
    result = QSignalSpy(runner.result)
    error = QSignalSpy(runner.error)
    runner.start(game_data(), "engine", repository, Settings())
    worker = runner.workers[-1]
    assert worker.wait(3000)
    app.processEvents()
    runner.shutdown()
    assert error.count() == 0
    assert progress.count() >= 2
    assert result.count() == 1
    assert result.at(0)[0].analysis == expected
    with closing(sqlite3.connect(repository.path)) as connection:
        state = connection.execute("SELECT state FROM analysis_runs").fetchone()[0]
    assert state == "complete"


def test_coach_runner_cancels_without_error(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = Event()

    class BlockingService:
        def __init__(self, cache=None) -> None:
            pass

        def analyze(self, *args, cancelled, **kwargs):
            started.set()
            assert cancelled.wait(2)
            raise AnalysisCancelled("cancelled")

    monkeypatch.setattr("chesscoach.coach.worker.GameAnalysisService", BlockingService)
    runner = CoachRunner()
    result = QSignalSpy(runner.result)
    error = QSignalSpy(runner.error)
    runner.start(
        game_data(),
        "engine",
        CoachRepository(tmp_path / "coach.sqlite3"),
        Settings(),
    )
    # Windows hosted runners can spend over a second creating the SQLite schema
    # before the worker reaches the blocking service. Keep the synchronization
    # bounded while allowing normal runner startup variance.
    assert started.wait(5)
    runner.shutdown()
    app.processEvents()
    assert result.count() == error.count() == 0


def test_coach_worker_redacts_secret_from_failure(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "sk-test-secret"

    class FailingService:
        def __init__(self, cache=None) -> None:
            pass

        def analyze(self, *args, **kwargs):
            raise RuntimeError(f"request failed with {secret}")

    monkeypatch.setattr("chesscoach.coach.worker.GameAnalysisService", FailingService)
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    runner = CoachRunner()
    errors = QSignalSpy(runner.error)
    runner.start(
        game_data(),
        "engine",
        repository,
        Settings(openai_api_key=secret, openai_model="model"),
    )
    assert runner.workers[-1].wait(3000)
    app.processEvents()
    assert errors.count() == 1
    assert secret not in errors.at(0)[0]
    with closing(sqlite3.connect(repository.path)) as connection:
        stored = connection.execute("SELECT error FROM analysis_runs").fetchone()[0]
    assert secret not in stored
