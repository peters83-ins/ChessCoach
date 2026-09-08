from dataclasses import replace

import chess
import chess.engine

from chesscoach.coach.models import EngineScore, MoveClassification
from chesscoach.coach.scoring import (
    classify_move,
    engine_score,
    move_accuracy,
    move_loss,
    pov_score,
    white_win_probability,
)


def test_scores_are_white_normalized_and_symmetric() -> None:
    positive = EngineScore(centipawns=250)
    negative = EngineScore(centipawns=-250)
    assert 0.68 < white_win_probability(positive) < 0.70
    assert white_win_probability(positive) == 1 - white_win_probability(negative)
    assert engine_score(chess.engine.PovScore(chess.engine.Cp(125), chess.BLACK)) == EngineScore(
        centipawns=-125
    )
    assert white_win_probability(EngineScore(mate=3)) == 0.99
    assert pov_score(positive).white().score() == 250


def test_loss_classification_and_accuracy() -> None:
    best = EngineScore(centipawns=200)
    played = EngineScore(centipawns=0)
    loss = move_loss(best, played, chess.WHITE)
    assert 15 < loss < 16
    assert (
        classify_move(
            loss,
            played_is_best=False,
            best=best,
            played=played,
            mover=chess.WHITE,
        )
        == MoveClassification.MISTAKE
    )
    assert move_accuracy(20) == 70
    assert (
        classify_move(
            1,
            played_is_best=True,
            best=best,
            played=replace(played, centipawns=190),
            mover=chess.WHITE,
        )
        == MoveClassification.BEST
    )


def test_missing_or_allowing_mate_is_a_blunder() -> None:
    assert (
        classify_move(
            1,
            played_is_best=False,
            best=EngineScore(mate=2),
            played=EngineScore(centipawns=500),
            mover=chess.WHITE,
        )
        == MoveClassification.BLUNDER
    )
    assert (
        classify_move(
            1,
            played_is_best=False,
            best=EngineScore(centipawns=0),
            played=EngineScore(mate=2),
            mover=chess.BLACK,
        )
        == MoveClassification.BLUNDER
    )
