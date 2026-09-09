from datetime import UTC, datetime

from chesscoach.coach.adaptive import LearningItem, compose_daily_session, next_course_due


def test_daily_session_uses_target_mix_and_fills_missing_categories():
    personal = tuple(LearningItem("personal", str(i)) for i in range(5))
    course = tuple(LearningItem("course", str(i)) for i in range(3))
    reinforcement = tuple(LearningItem("concept", str(i)) for i in range(2))
    session = compose_daily_session(personal, course, reinforcement)
    assert len(session) == 10
    assert [item.source for item in session].count("personal") == 5
    assert [item.source for item in session].count("course") == 3
    assert [item.source for item in session].count("concept") == 2


def test_daily_session_is_deterministic_and_fills_empty_pool():
    personal = (LearningItem("personal", "p"),)
    course = (LearningItem("course", "c"),)
    session = compose_daily_session(personal, course, (), limit=4)
    assert session == (personal[0], course[0])
    assert compose_daily_session((), (), (), limit=4) == ()


def test_course_schedule_starts_with_four_hour_review():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert next_course_due(0, True, now).startswith("2026-01-01T04:00")
    assert next_course_due(2, True, now).startswith("2026-01-04")
    assert next_course_due(4, False, now).startswith("2026-01-01T04:00")
