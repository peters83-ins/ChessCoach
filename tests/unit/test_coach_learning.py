from datetime import UTC, datetime

import chess

from chesscoach.coach.lessons import generate_lessons
from chesscoach.coach.models import (
    EngineScore,
    Evidence,
    GamePhase,
    MoveAnalysis,
    MoveClassification,
    PracticeItem,
    WeaknessEvent,
)
from chesscoach.coach.practice import generate_practice_items, schedule_attempt
from chesscoach.coach.weakness import aggregate_weaknesses, weakness_events
from chesscoach.storage.coach import CoachRepository


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


def test_old_weakness_evidence_decays() -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    recent = WeaknessEvent("p", "g", 1, "fork", 2, 1, observed_at=now.isoformat())
    old = WeaknessEvent("p", "g2", 1, "material", 2, 1, observed_at="2025-06-01T00:00:00+00:00")
    scores = {item.theme: item.score for item in aggregate_weaknesses((recent, old), now=now)}
    assert scores["fork"] > scores["material"]


def test_one_game_cannot_dominate_a_weakness() -> None:
    now = datetime(2026, 6, 1, tzinfo=UTC)
    events = (
        WeaknessEvent("p", "one-game", 1, "fork", 3, 1, observed_at=now.isoformat()),
        WeaknessEvent("p", "one-game", 3, "fork", 3, 1, observed_at=now.isoformat()),
        WeaknessEvent("p", "other-game", 1, "material", 2, 1, observed_at=now.isoformat()),
    )
    scores = {item.theme: item for item in aggregate_weaknesses(events, now=now)}
    assert scores["fork"].score == 3
    assert scores["fork"].occurrences == 1


def test_repository_tracks_previously_failed_practice_items(tmp_path) -> None:
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    item = PracticeItem(
        "item", "default", "game", 1, chess.STARTING_FEN, "fork", ("e2e4",), due_at=""
    )
    repository.save_learning((), (item,), ())
    assert repository.previously_failed_practice_ids() == frozenset()
    repository.record_practice_attempt(item, "f2f3", False)
    assert repository.previously_failed_practice_ids() == frozenset({"item"})
