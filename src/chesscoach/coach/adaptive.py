"""Deterministic daily learning selection and per-decision scheduling."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

COURSE_INTERVALS = (
    timedelta(hours=4),
    timedelta(days=1),
    timedelta(days=3),
    timedelta(days=7),
    timedelta(days=14),
    timedelta(days=30),
    timedelta(days=90),
)


@dataclass(frozen=True)
class LearningItem:
    source: str
    identifier: str
    theme: str = ""


def next_course_due(level: int, successful: bool, now: datetime | None = None) -> str:
    """Return the next local review time for one course decision."""
    current = now or datetime.now(UTC)
    index = min(max(level, 0), len(COURSE_INTERVALS) - 1)
    delay = COURSE_INTERVALS[index] if successful else COURSE_INTERVALS[0]
    return (current + delay).isoformat()


def compose_daily_session(
    personal: tuple[LearningItem, ...],
    course: tuple[LearningItem, ...],
    reinforcement: tuple[LearningItem, ...],
    limit: int = 10,
) -> tuple[LearningItem, ...]:
    """Choose a stable 50/30/20 mix, filling unavailable categories in order."""
    if limit <= 0:
        return ()
    targets = (limit * 5 // 10, limit * 3 // 10, limit * 2 // 10)
    pools = [list(personal), list(course), list(reinforcement)]
    selected: list[LearningItem] = []
    for index, target in enumerate(targets):
        selected.extend(pools[index][:target])
        pools[index] = pools[index][target:]
    # Fill short categories without randomization, preserving the requested order.
    remaining = limit - len(selected)
    for pool in pools:
        selected.extend(pool[:remaining])
        remaining = limit - len(selected)
        if not remaining:
            break
    # If a category had fewer than its target, its unused tail was already consumed above.
    return tuple(selected[:limit])
