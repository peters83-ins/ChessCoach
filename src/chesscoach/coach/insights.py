"""Transparent local learning and transfer metrics."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from chesscoach.chess.openings import OpeningMatch, OpeningStatistic, aggregate_openings


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
