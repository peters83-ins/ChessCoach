import chess
import chess.engine

from chesscoach.engine.analysis import CandidateLine, PositionAnalysis


def test_best_move_and_empty_analysis() -> None:
    assert PositionAnalysis(chess.STARTING_FEN, ()).best_move is None
    score = chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE)
    first = chess.Move.from_uci("e2e4")
    line = CandidateLine(score, (first, chess.Move.from_uci("e7e5")), 12)
    analysis = PositionAnalysis(chess.STARTING_FEN, (line,))
    assert analysis.best_move == first
    assert analysis.candidates[0].score.white().score() == 20
    assert PositionAnalysis(chess.STARTING_FEN, (CandidateLine(score, (), 0),)).best_move is None
