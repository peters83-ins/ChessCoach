from datetime import UTC, datetime

import chess

from chesscoach.coach.lessons import generate_lessons
from chesscoach.coach.models import (
    EngineScore,
    Evidence,
    GamePhase,
    MoveAnalysis,
    MoveClassification,
)
from chesscoach.coach.practice import generate_practice_items, schedule_attempt
from chesscoach.coach.weakness import aggregate_weaknesses, weakness_events


def mistake() -> MoveAnalysis:
    return MoveAnalysis(
        1,
        chess.STARTING_FEN,
        "white",
        "f2f3",
        "f3",
        "e2e4",
        "e4",
        EngineScore(centipawns=50),
        EngineScore(centipawns=-100),
        12,
        82,
        MoveClassification.MISTAKE,
        GamePhase.OPENING,
        ("e2e4", "e7e5"),
        ("f2f3", "e7e5"),
        14,
        (Evidence("fact", "opening_development", "Develop toward the center."),),
        ("opening_development",),
    )


def test_weaknesses_generate_scheduled_practice_and_lessons() -> None:
    move = mistake()
    events = weakness_events("default", "game", (move,), "white")
    weaknesses = aggregate_weaknesses(events)
    assert weaknesses[0].theme == "opening_development"
    items = generate_practice_items("default", "game", (move, move))
    assert len(items) == 1
    assert items[0].validate_attempt(chess.Move.from_uci("e2e4"))
    assert not items[0].validate_attempt(chess.Move.from_uci("f2f3"))
    scheduled = schedule_attempt(
        items[0], successful=True, attempted_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert scheduled.interval_days == 3
    assert scheduled.due_at.startswith("2026-01-04")
    lessons = generate_lessons("default", weaknesses, items)
    assert lessons[0].title == "Efficient Development"
    assert lessons[0].exercise_ids == (items[0].id,)
