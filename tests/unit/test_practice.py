import random
from collections import Counter

import chess
import chess.engine

from chesscoach.engine.analysis import CandidateLine, PositionAnalysis
from chesscoach.engine.practice import practice_move


def test_practice_levels_have_distinct_error_rates_and_legal_choices() -> None:
    board = chess.Board()
    moves = sorted(board.legal_moves, key=lambda move: move.uci())[:8]
    candidates = tuple(
        CandidateLine(chess.engine.PovScore(chess.engine.Cp(-i * 80), chess.WHITE), (move,), 8)
        for i, move in enumerate(moves)
    )
    losses = {}
    for level in (800, 1000, 1200):
        selections = Counter()
        for sample in range(200):
            analysis = PositionAnalysis(f"sample-{sample}", candidates)
            chosen = practice_move(analysis, chess.WHITE, level, rng=random.Random(sample))
            assert chosen in board.legal_moves
            assert practice_move(analysis, chess.WHITE, level, rng=random.Random(sample)) == chosen
            selections[moves.index(chosen)] += 1
        losses[level] = sum(index * count for index, count in selections.items())
    assert losses[800] > losses[1000] > losses[1200]


def test_black_scores_are_interpreted_from_black_perspective() -> None:
    best, worst = chess.Move.from_uci("e7e5"), chess.Move.from_uci("f7f6")
    analysis = PositionAnalysis(
        "black",
        (
            CandidateLine(chess.engine.PovScore(chess.engine.Mate(-1), chess.WHITE), (best,), 10),
            CandidateLine(chess.engine.PovScore(chess.engine.Mate(1), chess.WHITE), (worst,), 10),
        ),
    )
    assert practice_move(analysis, chess.BLACK, 800, rng=random.Random(1)) == best


def test_practice_selection_can_vary_for_identical_position() -> None:
    moves = tuple(chess.Move.from_uci(uci) for uci in ("e2e4", "d2d4", "g1f3", "c2c4"))
    analysis = PositionAnalysis(
        "same-position",
        tuple(
            CandidateLine(chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE), (move,), 8)
            for move in moves
        ),
    )
    choices = {
        practice_move(analysis, chess.WHITE, 1000, rng=random.Random(seed)) for seed in range(12)
    }
    assert len(choices) > 1
