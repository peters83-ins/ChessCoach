from unittest.mock import MagicMock, patch

import chess
import chess.engine
import pytest

from chesscoach.engine.stockfish import Stockfish


@pytest.fixture
def engine() -> Stockfish:
    with patch("chess.engine.SimpleEngine.popen_uci") as start:
        service = Stockfish("test-engine")
        start.return_value.options = {
            "UCI_Elo": chess.engine.Option("UCI_Elo", "spin", 1500, 1500, 2800, None),
            "UCI_LimitStrength": object(),
        }
        yield service
        service.close()


def test_difficulty_clamps_to_supported_range(engine: Stockfish) -> None:
    assert engine.configure_difficulty(1400) == 1500
    engine._engine.configure.assert_called_with({"UCI_LimitStrength": True, "UCI_Elo": 1500})
    assert engine.configure_difficulty(9999) == 2800


@pytest.mark.parametrize("level", [800, 1000, 1200])
def test_practice_setting_not_silently_clamped(engine: Stockfish, level: int) -> None:
    assert engine.configure_difficulty(level) == level
    assert engine.practice_level == level
    engine._engine.configure.assert_called_with({"UCI_LimitStrength": True, "UCI_Elo": 1500})


def test_missing_or_unsupported_engine(engine: Stockfish) -> None:
    with pytest.raises(ValueError, match="executable"):
        Stockfish("")
    engine._engine.options = {}
    with pytest.raises(ValueError, match="difficulty"):
        engine.configure_difficulty(1400)


def test_legal_and_illegal_engine_moves(engine: Stockfish) -> None:
    engine._engine.play.return_value = chess.engine.PlayResult(chess.Move.from_uci("e2e4"), None)
    assert engine.play(chess.Board()).uci() == "e2e4"
    for move in (None, chess.Move.from_uci("e2e5")):
        engine._engine.play.return_value = chess.engine.PlayResult(move, None)
        with pytest.raises(ValueError, match="legal move"):
            engine.play(chess.Board())


def test_full_strength_analysis_normalizes_score_and_validates_pv(engine: Stockfish) -> None:
    backend: MagicMock = engine._engine
    backend.analyse.return_value = [
        {
            "score": chess.engine.PovScore(chess.engine.Cp(-34), chess.BLACK),
            "pv": [chess.Move.from_uci("e2e4")],
            "depth": 12,
        }
    ]
    root = chess.Move.from_uci("e2e4")
    result = engine.analyze(
        chess.Board(),
        limit=chess.engine.Limit(time=0.1),
        root_moves=(root,),
        pv_plies=1,
    )
    assert result.candidates[0].score.white().score() == 34
    assert result.best_move.uci() == "e2e4"
    assert backend.analyse.call_args.kwargs["options"] == {"UCI_LimitStrength": False}
    assert backend.analyse.call_args.kwargs["root_moves"] == (root,)
    assert len(result.candidates[0].moves) == 1
    backend.analyse.return_value[0]["pv"] = [chess.Move.from_uci("e2e5")]
    with pytest.raises(ValueError, match="principal variation"):
        engine.analyze(chess.Board(), limit=chess.engine.Limit(time=0.1))
    with pytest.raises(ValueError, match="Root analysis"):
        engine.analyze(
            chess.Board(),
            limit=chess.engine.Limit(time=0.1),
            root_moves=(chess.Move.from_uci("e2e5"),),
        )
