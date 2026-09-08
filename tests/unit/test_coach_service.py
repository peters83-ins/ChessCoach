from dataclasses import replace

import chess
import chess.engine

from chesscoach.chess.pgn import parse_pgn
from chesscoach.coach.models import AnalysisProfile
from chesscoach.coach.service import GameAnalysisService
from chesscoach.engine.analysis import CandidateLine, PositionAnalysis
from chesscoach.storage.database import GameData


class MemoryCache:
    def __init__(self) -> None:
        self.values = {}

    def get_move_analysis(self, key: str):
        return self.values.get(key)

    def put_move_analysis(self, key: str, analysis) -> None:
        self.values[key] = analysis


class FakeEngine:
    signature = "Fake 1"
    calls = 0
    closed = 0

    def __init__(self, path: str) -> None:
        assert path == "engine"

    def analyze(
        self, position, *, limit, multipv=1, root_moves=None, pv_plies=None
    ) -> PositionAnalysis:
        type(self).calls += 1
        move = root_moves[0] if root_moves else chess.Move.from_uci("e2e4")
        reply = chess.Move.from_uci("e7e5")
        cp = -100 if move == chess.Move.from_uci("f2f3") else 100
        line = CandidateLine(
            chess.engine.PovScore(chess.engine.Cp(cp), chess.WHITE), (move, reply), 14
        )
        return PositionAnalysis(position.fen(), (line,))

    def close(self) -> None:
        type(self).closed += 1


def game_data() -> GameData:
    return GameData.from_game(
        parse_pgn("1. f3 *"),
        match_id="game-1",
        started_at="start",
        saved_at="saved",
        ended_at=None,
        player_color=chess.WHITE,
        bot_elo=1000,
        move_timestamps=("move",),
    )


def test_adaptive_analysis_deepens_and_reuses_cache() -> None:
    FakeEngine.calls = FakeEngine.closed = 0
    cache = MemoryCache()
    updates = []
    service = GameAnalysisService(FakeEngine, cache)
    profile = AnalysisProfile(quick_time=0.01, deep_time=0.02)
    analysis = service.analyze(game_data(), "engine", profile, progress=updates.append)
    assert analysis.moves[0].deepened
    assert analysis.moves[0].best_uci == "e2e4"
    assert analysis.moves[0].played_uci == "f2f3"
    assert analysis.turning_points == (1,)
    assert FakeEngine.calls == 4
    assert updates[-1].stage == "deep"
    assert FakeEngine.closed == 1

    calls = FakeEngine.calls
    repeated = service.analyze(game_data(), "engine", replace(profile))
    assert repeated == analysis
    assert FakeEngine.calls == calls
    assert FakeEngine.closed == 2
