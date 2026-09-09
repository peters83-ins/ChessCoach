"""Transparent local learning and transfer metrics."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from chesscoach.chess.openings import (
    OpeningMatch,
    OpeningStatistic,
    aggregate_openings,
    recognize_opening,
)
from chesscoach.coach.models import MoveAnalysis


@dataclass(frozen=True)
class LearningInsights:
    games: int
    opening_stats: tuple[OpeningStatistic, ...]
    due_reviews: int
    weakest_theme: str
    recommendation: str


@dataclass(frozen=True)
class TransferMetric:
    theme: str
    before_rate: float
    after_rate: float
    sample_size: int

    @property
    def delta(self) -> float:
        return self.after_rate - self.before_rate


def opening_stats(
    records: Iterable[tuple[OpeningMatch, str, str]], *, min_games: int = 5
) -> tuple[OpeningStatistic, ...]:
    """Return opening results only when the sample reaches the transparent threshold."""
    return aggregate_openings(records, min_games=min_games)


def recency_weighted_average(
    values: Iterable[tuple[float, datetime]], now: datetime | None = None
) -> float:
    """Weight recent observations more heavily with a simple 30-day decay."""
    current = now or datetime.now(UTC)
    weighted = 0.0
    total = 0.0
    for value, observed in values:
        age_days = max(0.0, (current - observed).total_seconds() / 86400)
        weight = 1.0 / (1.0 + age_days / 30.0)
        weighted += value * weight
        total += weight
    return weighted / total if total else 0.0


def period_comparison(
    values: Iterable[tuple[float, datetime]],
    *,
    now: datetime | None = None,
    recent_days: int = 45,
    minimum: int = 3,
) -> tuple[float, float] | None:
    """Return weighted recent and prior averages once both periods have data."""
    current = now or datetime.now(UTC)
    recent: list[tuple[float, datetime]] = []
    prior: list[float] = []
    for value, observed in values:
        age_days = (current - observed).total_seconds() / 86400
        if 0 <= age_days <= recent_days:
            recent.append((value, observed))
        elif age_days > recent_days:
            prior.append(value)
    if len(recent) < minimum or len(prior) < minimum:
        return None
    recent_average = recency_weighted_average(recent, current)
    return recent_average, sum(prior) / len(prior)


def recommend_next_action(due_reviews: int, weakest_theme: str, games: int) -> str:
    """Rank one actionable next step instead of presenting an unranked dashboard."""
    if due_reviews:
        return f"Complete {min(due_reviews, 10)} due practice decision(s)."
    if weakest_theme:
        return f"Practice one position about {weakest_theme.replace('_', ' ')}."
    if games:
        return "Review your latest saved game for a new practice position."
    return "Play or import a game to start building local learning insights."


def theme_frequency(themes: Iterable[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for theme in themes:
        counts[theme] = counts.get(theme, 0) + 1
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def transfer_metric(
    theme: str, before: tuple[bool, ...], after: tuple[bool, ...], *, minimum: int = 5
) -> TransferMetric | None:
    """Compare success rates only when both periods have enough observations."""
    if len(before) < minimum or len(after) < minimum:
        return None
    return TransferMetric(
        theme, sum(before) / len(before), sum(after) / len(after), len(before) + len(after)
    )


def phase_accuracy(
    moves: Iterable[MoveAnalysis], player_color: str | None = None
) -> tuple[tuple[str, float, int], ...]:
    grouped: dict[str, list[float]] = {}
    for move in moves:
        if player_color is not None and move.mover != player_color:
            continue
        grouped.setdefault(move.phase.value, []).append(move.accuracy)
    return tuple(
        (phase, sum(values) / len(values), len(values)) for phase, values in sorted(grouped.items())
    )


def phase_transfer(
    records: Iterable[tuple[str, float, datetime]],
    *,
    now: datetime | None = None,
    minimum: int = 3,
) -> tuple[tuple[str, float, float, int], ...]:
    """Compare phase accuracy in recent versus earlier analyzed games."""
    grouped: dict[str, tuple[list[float], list[float]]] = {}
    current = now or datetime.now(UTC)
    for phase, accuracy, observed in records:
        recent, prior = grouped.setdefault(phase, ([], []))
        age_days = (current - observed).total_seconds() / 86400
        (recent if 0 <= age_days <= 45 else prior).append(accuracy)
    return tuple(
        (phase, sum(recent) / len(recent), sum(prior) / len(prior), len(recent) + len(prior))
        for phase, (recent, prior) in sorted(grouped.items())
        if len(recent) >= minimum and len(prior) >= minimum
    )


def opening_departure_transfer(
    records: Iterable[tuple[tuple[str, ...], datetime]],
    *,
    now: datetime | None = None,
    minimum: int = 3,
) -> tuple[float, float, int] | None:
    """Compare the fraction of each game that follows a reviewed opening line."""
    current = now or datetime.now(UTC)
    recent: list[float] = []
    prior: list[float] = []
    for moves, observed in records:
        opening = recognize_opening(moves)
        if opening is None or not moves:
            continue
        rate = opening.book_plies / len(moves)
        age_days = (current - observed).total_seconds() / 86400
        if 0 <= age_days <= 45:
            recent.append(rate)
        elif age_days > 45:
            prior.append(rate)
    if len(recent) < minimum or len(prior) < minimum:
        return None
    return sum(recent) / len(recent), sum(prior) / len(prior), len(recent) + len(prior)


def analyzed_theme_counts(moves: Iterable[MoveAnalysis]) -> tuple[tuple[str, int], ...]:
    return theme_frequency(tag for move in moves for tag in move.tags)
