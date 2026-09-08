"""Deterministic full-game summaries linked to analyzed plies."""

from collections import Counter

from chesscoach.coach.models import GameAnalysis, GameReport, MoveClassification, WeaknessScore


def build_report(
    analysis: GameAnalysis, player_color: str, weaknesses: tuple[WeaknessScore, ...]
) -> GameReport:
    player_moves = tuple(move for move in analysis.moves if move.mover == player_color)
    strongest = tuple(
        move.ply
        for move in sorted(player_moves, key=lambda item: (-item.accuracy, item.ply))
        if move.classification in (MoveClassification.BEST, MoveClassification.EXCELLENT)
    )[:3]
    counts = Counter(move.classification.value for move in player_moves)
    inaccuracy_word = "inaccuracy" if counts["inaccuracy"] == 1 else "inaccuracies"
    summary = (
        f"Accuracy {analysis.player_accuracy:.1f}%. "
        f"{counts['blunder']} blunder(s), {counts['mistake']} mistake(s), and "
        f"{counts['inaccuracy']} {inaccuracy_word}."
    )
    return GameReport(
        analysis.player_accuracy,
        summary,
        strongest,
        tuple(
            ply for ply in analysis.turning_points if analysis.moves[ply - 1].mover == player_color
        ),
        tuple(weakness.theme for weakness in weaknesses[:5]),
        analysis.phase_summaries,
    )
