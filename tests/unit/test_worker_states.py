from chesscoach.coach.worker import CoachRunner, CoachWorkerState
from chesscoach.engine.worker import EngineRunner, WorkerState


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
