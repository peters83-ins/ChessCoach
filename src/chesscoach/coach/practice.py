"""Practice generation and deterministic spaced repetition."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from chesscoach.coach.models import MoveAnalysis, MoveClassification, PracticeItem

INTERVALS = (1, 3, 7, 14, 30)


def generate_practice_items(
    profile_id: str,
    game_id: str,
    moves: tuple[MoveAnalysis, ...],
    player_color: str | None = None,
) -> tuple[PracticeItem, ...]:
    items: dict[tuple[str, str], PracticeItem] = {}
    now = datetime.now(UTC)
    for move in moves:
        if (
            (player_color is not None and move.mover != player_color)
            or move.classification
            not in (
                MoveClassification.INACCURACY,
                MoveClassification.MISTAKE,
                MoveClassification.BLUNDER,
            )
            or not move.best_pv
        ):
            continue
        normalized_fen = " ".join(move.fen.split()[:4])
        for theme in move.tags or ("calculation",):
            key = (normalized_fen, theme)
            identifier = str(uuid5(NAMESPACE_URL, f"{profile_id}:{game_id}:{move.ply}:{theme}"))
            items[key] = PracticeItem(
                identifier,
                profile_id,
                game_id,
                move.ply,
                move.fen,
                theme,
                move.best_pv[:3],
                move.alternative_moves,
                due_at=now.isoformat(),
            )
    return tuple(items.values())


def schedule_attempt(
    item: PracticeItem, *, successful: bool, attempted_at: datetime | None = None
) -> PracticeItem:
    now = attempted_at or datetime.now(UTC)
    if successful:
        current_index = min(
            range(len(INTERVALS)), key=lambda i: abs(INTERVALS[i] - item.interval_days)
        )
        interval = INTERVALS[min(current_index + 1, len(INTERVALS) - 1)]
        ease = min(3.0, item.ease + 0.1)
    else:
        interval = 1
        ease = max(1.3, item.ease - 0.2)
    return replace(
        item,
        interval_days=interval,
        ease=round(ease, 2),
        due_at=(now + timedelta(days=interval)).isoformat(),
    )
