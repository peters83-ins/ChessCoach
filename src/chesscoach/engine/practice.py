"""Approximate beginner opponents, not calibrated Elo ratings."""

import math
import random
from typing import TypeAlias

import chess

from chesscoach.engine.analysis import PositionAnalysis

TEMPERATURES = {800: 180.0, 1000: 100.0, 1200: 45.0}
RandomSource: TypeAlias = random.Random | random.SystemRandom


def practice_move(
    analysis: PositionAnalysis,
    turn: chess.Color,
    level: int,
    *,
    rng: RandomSource | None = None,
) -> chess.Move:
    """Sample engine-ranked legal moves, allowing more errors at easier levels.

    Limited-strength play samples a legal, engine-ranked move on each turn. The
    default system random source prevents an opponent from repeating the same
    response to an identical position, while an injected source keeps tests and
    replay tools reproducible. Engine evaluations themselves are never weakened
    or fabricated.
    """
    lines = sorted(
        (line for line in analysis.candidates if line.moves),
        key=lambda line: line.moves[0].uci(),
    )
    if not lines:
        raise ValueError("Stockfish returned no candidate moves.")
    scores = [line.score.pov(turn).score(mate_score=100_000) for line in lines]
    values = [float(score) for score in scores if score is not None]
    if len(values) != len(lines):
        raise ValueError("Stockfish returned an unknown evaluation.")
    best = max(values)
    weights = [math.exp((score - best) / TEMPERATURES[level]) for score in values]
    chooser = rng or random.SystemRandom()
    return chooser.choices(lines, weights=weights, k=1)[0].moves[0]
