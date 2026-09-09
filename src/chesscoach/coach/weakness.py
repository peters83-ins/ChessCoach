"""Persistent weakness scoring from grounded move evidence."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

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
            events.append(
                WeaknessEvent(
                    profile_id,
                    game_id,
                    move.ply,
                    theme,
                    severity,
                    1.0,
                    observed_at=datetime.now(UTC).isoformat(),
                )
            )
    return tuple(events)


def aggregate_weaknesses(
    events: Iterable[WeaknessEvent], *, now: datetime | None = None
) -> tuple[WeaknessScore, ...]:
    reference = now or datetime.now(UTC)
    grouped: dict[tuple[str, str, str], float] = {}
    theme_events: dict[str, int] = defaultdict(int)
    for index, event in enumerate(events):
        direction = -0.5 if event.outcome == "mastered" else 1.0
        recency = 1.0
        if event.observed_at:
            observed = datetime.fromisoformat(event.observed_at)
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            age_days = max(0.0, (reference - observed).total_seconds() / 86_400)
            recency = 0.5 ** (age_days / 90)
        contribution = direction * event.severity * event.confidence * recency
        source = event.game_id or f"event-{index}"
        key = (event.theme, source, event.outcome)
        current = grouped.get(key)
        if current is None or abs(contribution) > abs(current):
            grouped[key] = contribution
    totals: dict[str, float] = defaultdict(float)
    for (theme, _, _), contribution in grouped.items():
        totals[theme] += contribution
        theme_events[theme] += 1
    return tuple(
        WeaknessScore(theme, round(max(0.0, score), 2), theme_events[theme])
        for theme, score in sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    )
