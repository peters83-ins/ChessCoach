import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path

import chess
import chess.engine

from chesscoach.chess.pgn import parse_pgn
from chesscoach.coach.feedback import LocalTemplateProvider
from chesscoach.coach.lessons import generate_lessons
from chesscoach.coach.models import AnalysisProfile, CoachingContext
from chesscoach.coach.pipeline import CoachPipeline
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


class CloudProvider:
    name = "openai"
    model = "model"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, contexts):
        self.calls += 1
        local = LocalTemplateProvider().generate(contexts)
        return tuple(
            replace(
                item,
                provider=self.name,
                model=self.model,
                context_hash=context.context_hash,
            )
            for item, context in zip(local, contexts, strict=True)
        )


def test_feedback_cache_uses_model_prompt_and_context(tmp_path: Path) -> None:
    path = tmp_path / "games.sqlite3"
    game = saved_game(path)
    repository = CoachRepository(path)
    analysis = GameAnalysisService(FakeEngine, repository).analyze(
        game, "engine", AnalysisProfile(quick_time=0.01, deep_time=0.02)
    )
    provider = CloudProvider()
    first = CoachPipeline(repository).build(game, analysis, provider)
    second = CoachPipeline(repository).build(game, analysis, provider)
    assert provider.calls == 1
    assert first.feedback == second.feedback
    assert CoachingContext(game.id, analysis.moves[0]).context_hash


def test_version_one_feedback_schema_migrates_without_data_loss(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute(
            "CREATE TABLE coach_feedback (game_id TEXT, ply INTEGER, provider TEXT, "
            "prompt_version TEXT, data_json TEXT, created_at TEXT, "
            "PRIMARY KEY(game_id, ply, provider, prompt_version))"
        )
        connection.execute(
            "INSERT INTO coach_feedback VALUES ('game', 1, 'local', 'v1', '{}', 'now')"
        )
    CoachRepository(path).migrate()
    with closing(sqlite3.connect(path)) as connection:
        columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(coach_feedback)"))
        row = connection.execute(
            "SELECT game_id, model, context_hash FROM coach_feedback"
        ).fetchone()
        version = connection.execute(
            "SELECT version FROM schema_versions WHERE component='coach'"
        ).fetchone()[0]
    assert "model" in columns and "context_hash" in columns
    assert row == ("game", "", "")
    assert version == 2


def test_latest_run_status_supports_resume(tmp_path: Path) -> None:
    repository = CoachRepository(tmp_path / "games.sqlite3")
    run_id = repository.start_run("game", AnalysisProfile())
    repository.update_run(run_id, "cancelled", 3, 10)
    status = repository.latest_run_status("game")
    assert status is not None
    assert (status.state, status.completed, status.total) == ("cancelled", 3, 10)
