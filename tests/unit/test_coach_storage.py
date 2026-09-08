from pathlib import Path

import chess
import chess.engine

from chesscoach.chess.pgn import parse_pgn
from chesscoach.coach.lessons import generate_lessons
from chesscoach.coach.models import AnalysisProfile
from chesscoach.coach.practice import generate_practice_items
from chesscoach.coach.service import GameAnalysisService
from chesscoach.coach.weakness import weakness_events
from chesscoach.engine.analysis import CandidateLine, PositionAnalysis
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameData, GameDatabase


class FakeEngine:
    signature = "Fake"

    def __init__(self, path: str) -> None:
        pass

    def analyze(self, position, *, limit, multipv=1, root_moves=None, pv_plies=None):
        move = root_moves[0] if root_moves else chess.Move.from_uci("e2e4")
        cp = -100 if root_moves else 100
        line = CandidateLine(
            chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE),
            (move, chess.Move.from_uci("e7e5")),
            12,
        )
        return PositionAnalysis(position.fen(), (line,))

    def close(self) -> None:
        pass


def saved_game(path: Path) -> GameData:
    data = GameData.from_game(
        parse_pgn("1. f3 *"),
        match_id="stored-game",
        started_at="start",
        saved_at="saved",
        ended_at=None,
        player_color=chess.WHITE,
        bot_elo=1000,
        move_timestamps=("move",),
    )
    assert GameDatabase(path).save_game(data).success
    return data


def test_analysis_cache_runs_and_learning_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "games" / "games.sqlite3"
    data = saved_game(path)
    repository = CoachRepository(path)
    profile = AnalysisProfile(quick_time=0.01, deep_time=0.02)
    analysis = GameAnalysisService(FakeEngine, repository).analyze(data, "engine", profile)
    run_id = repository.start_run(data.id, analysis.profile)
    repository.save_analysis(run_id, analysis)
    assert repository.load_latest_analysis(data.id) == analysis

    events = weakness_events("default", data.id, analysis.moves, data.player_color)
    items = generate_practice_items("default", data.id, analysis.moves)
    assert not repository.weakness_scores()
    from chesscoach.coach.weakness import aggregate_weaknesses

    lessons = generate_lessons("default", aggregate_weaknesses(events), items)
    repository.save_learning(events, items, lessons)
    repository.save_learning(events, items, lessons)
    assert repository.weakness_scores()[0].occurrences == 1
    assert repository.practice_items() == items
    assert repository.lessons() == lessons
