"""Persistent weakness scoring from grounded move evidence."""

from collections import defaultdict
from collections.abc import Iterable

from chesscoach.coach.models import MoveAnalysis, MoveClassification, WeaknessEvent, WeaknessScore

SEVERITY = {
    MoveClassification.INACCURACY: 1.0,
    MoveClassification.MISTAKE: 2.0,
    MoveClassification.BLUNDER: 3.0,
}


def weakness_events(
    profile_id: str, game_id: str, moves: Iterable[MoveAnalysis], player_color: str
) -> tuple[WeaknessEvent, ...]:
    events = []
    for move in moves:
        severity = SEVERITY.get(move.classification)
        if move.mover != player_color or severity is None:
            continue
        for theme in move.tags or ("calculation",):
            events.append(WeaknessEvent(profile_id, game_id, move.ply, theme, severity, 1.0))
    return tuple(events)


def aggregate_weaknesses(events: Iterable[WeaknessEvent]) -> tuple[WeaknessScore, ...]:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for event in events:
        direction = -0.5 if event.outcome == "mastered" else 1.0
        totals[event.theme] += direction * event.severity * event.confidence
        counts[event.theme] += 1
    return tuple(
        WeaknessScore(theme, round(max(0.0, score), 2), counts[theme])
        for theme, score in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    )
