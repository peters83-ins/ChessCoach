from chesscoach.courses.catalog import CourseCatalog
from chesscoach.storage.coach import CoachRepository


def course():
    return CourseCatalog.from_data(
        {
            "schema_version": 1,
            "courses": [
                {
                    "id": "demo",
                    "version": 2,
                    "title": "Demo",
                    "description": "",
                    "level_min": 600,
                    "level_max": 1400,
                    "side": "white",
                    "estimated_minutes": 5,
                    "modules": [
                        {"id": "m1", "title": "One", "summary": "", "exercise_ids": ["e1"]}
                    ],
                    "exercises": [
                        {
                            "id": "e1",
                            "module_id": "m1",
                            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                            "learner_color": "white",
                            "line": ["e2e4", "e7e5", "g1f3"],
                        }
                    ],
                }
            ],
        }
    ).courses[0]


def test_course_progress_and_decisions_are_additive(tmp_path):
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    item = course()
    repository.enroll_course(item)
    assert repository.course_progress("demo")[0].content_version == 2
    first = repository.record_course_attempt("demo", "e1", 0, "e2e4", True)
    second = repository.record_course_attempt("demo", "e1", 1, "g1f3", False, hints=1)
    assert (first.level, first.attempts, first.errors) == (1, 1, 0)
    assert (second.level, second.attempts, second.errors, second.hints) == (0, 1, 1, 1)
    assert len(repository.course_mastery("demo")) == 2
