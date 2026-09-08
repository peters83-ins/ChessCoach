"""Transparent score normalization and move grading."""

import math
from collections.abc import Iterable

import chess
import chess.engine

from chesscoach.coach.models import (
    EngineScore,
    GamePhase,
    MoveAnalysis,
    MoveClassification,
    PhaseSummary,
)


def engine_score(score: chess.engine.PovScore) -> EngineScore:
    white = score.white()
    mate = white.mate()
    return (
        EngineScore(mate=mate) if mate is not None else EngineScore(centipawns=white.score() or 0)
    )


def pov_score(score: EngineScore) -> chess.engine.PovScore:
    value: chess.engine.Score = (
        chess.engine.Mate(score.mate)
        if score.mate is not None
        else chess.engine.Cp(score.centipawns or 0)
    )
    return chess.engine.PovScore(value, chess.WHITE)


def white_win_probability(score: EngineScore) -> float:
    if score.mate is not None:
        return 0.99 if score.mate > 0 else 0.01
    assert score.centipawns is not None
    return 0.5 + 0.49 * math.tanh(score.centipawns / 600)


def move_loss(best: EngineScore, played: EngineScore, mover: chess.Color) -> float:
    best_white = white_win_probability(best)
    played_white = white_win_probability(played)
    loss = best_white - played_white if mover == chess.WHITE else played_white - best_white
    return round(max(0.0, loss * 100), 3)


def classify_move(
    loss_percent: float,
    *,
    played_is_best: bool,
    best: EngineScore,
    played: EngineScore,
    mover: chess.Color,
) -> MoveClassification:
    mover_sign = 1 if mover == chess.WHITE else -1
    missed_mate = best.mate is not None and best.mate * mover_sign > 0 and played.mate is None
    allowed_mate = (
        played.mate is not None
        and played.mate * mover_sign < 0
        and (best.mate is None or best.mate * mover_sign >= 0)
    )
    if missed_mate or allowed_mate or loss_percent >= 20:
        return MoveClassification.BLUNDER
    if loss_percent >= 10:
        return MoveClassification.MISTAKE
    if loss_percent >= 5:
        return MoveClassification.INACCURACY
    if played_is_best or loss_percent <= 0.5:
        return MoveClassification.BEST
    if loss_percent <= 2:
        return MoveClassification.EXCELLENT
    return MoveClassification.GOOD


def move_accuracy(loss_percent: float) -> float:
    return round(max(0.0, 100.0 - 1.5 * loss_percent), 1)


def game_phase(board: chess.Board) -> GamePhase:
    non_pawn_material = sum(
        len(board.pieces(piece_type, color)) * value
        for color in chess.COLORS
        for piece_type, value in (
            (chess.KNIGHT, 3),
            (chess.BISHOP, 3),
            (chess.ROOK, 5),
            (chess.QUEEN, 9),
        )
    )
    if board.fullmove_number <= 10 and non_pawn_material >= 50:
        return GamePhase.OPENING
    if non_pawn_material <= 24:
        return GamePhase.ENDGAME
    return GamePhase.MIDDLEGAME


def player_accuracy(moves: Iterable[MoveAnalysis], player_color: str) -> float:
    relevant = [move for move in moves if move.mover == player_color]
    if not relevant:
        return 0.0
    weights = [
        1.0
        + (1.0 - abs(white_win_probability(move.best_score) - 0.5) * 2)
        + (0.5 if move.loss_percent >= 10 else 0)
        for move in relevant
    ]
    return round(
        sum(move.accuracy * weight for move, weight in zip(relevant, weights, strict=True))
        / sum(weights),
        1,
    )


def phase_summaries(moves: Iterable[MoveAnalysis], player_color: str) -> tuple[PhaseSummary, ...]:
    relevant = tuple(move for move in moves if move.mover == player_color)
    summaries = []
    for phase in GamePhase:
        selected = tuple(move for move in relevant if move.phase == phase)
        if selected:
            summaries.append(
                PhaseSummary(
                    phase,
                    round(sum(move.accuracy for move in selected) / len(selected), 1),
                    sum(
                        move.classification
                        in (MoveClassification.MISTAKE, MoveClassification.BLUNDER)
                        for move in selected
                    ),
                    len(selected),
                )
            )
    return tuple(summaries)


def turning_points(moves: tuple[MoveAnalysis, ...]) -> tuple[int, ...]:
    result: list[int] = []
    for move in moves:
        previous_probability = white_win_probability(move.best_score)
        probability = white_win_probability(move.played_score)
        favored_changed = (previous_probability - 0.5) * (probability - 0.5) < 0
        crossed = any(
            (previous_probability - boundary) * (probability - boundary) < 0
            for boundary in (0.2, 0.4, 0.6, 0.8)
        )
        if (
            move.classification in (MoveClassification.MISTAKE, MoveClassification.BLUNDER)
            or favored_changed
            or crossed
            or move.best_score.mate is not None
            or move.played_score.mate is not None
        ):
            result.append(move.ply)
    return tuple(result)
