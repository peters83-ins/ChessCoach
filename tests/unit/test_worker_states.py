import chess
import chess.engine

from chesscoach.engine.analysis import CandidateLine, PositionAnalysis
from chesscoach.coach.worker import CoachRunner, CoachWorkerState
from chesscoach.engine.worker import EngineRunner, SearchResult, WorkerState


def test_engine_runner_starts_idle_and_closes_cleanly():
    runner = EngineRunner()
    assert runner.state == WorkerState.IDLE
    runner.shutdown()
    assert runner.state == WorkerState.CLOSED


def test_coach_runner_starts_idle_and_closes_cleanly():
    runner = CoachRunner()
    assert runner.state == CoachWorkerState.IDLE
    runner.shutdown()
    assert runner.state == CoachWorkerState.CLOSED


def test_engine_runner_rejects_stale_result_and_error() -> None:
    runner = EngineRunner()
    received: list[SearchResult] = []
    errors: list[str] = []
    runner.result.connect(received.append)
    runner.error.connect(errors.append)
    move = chess.Move.from_uci("e2e4")
    analysis = PositionAnalysis(
        chess.STARTING_FEN,
        (CandidateLine(chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE), (move,), 8),),
    )
    result = SearchResult(analysis, move, 1200)
    runner.generation = 4
    runner._result(3, result)
    runner._error(3, "stale")
    assert received == []
    assert errors == []
    assert runner.state == WorkerState.IDLE
    runner._result(4, result)
    assert received == [result]
    assert runner.state == WorkerState.READY
    runner._error(4, "engine failed")
    assert errors == ["engine failed"]
    assert runner.last_error == "engine failed"
    assert runner.state == WorkerState.FAILED
    runner.shutdown()


def test_engine_cancel_invalidates_generation_and_marks_cancelled() -> None:
    runner = EngineRunner()
    runner.state = WorkerState.SEARCHING
    generation = runner.generation
    runner.cancel()
    assert runner.generation == generation + 1
    assert runner.state == WorkerState.CANCELLED
    runner.shutdown()
