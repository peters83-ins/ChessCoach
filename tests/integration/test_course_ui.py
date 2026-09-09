from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.courses.catalog import CourseCatalog
from chesscoach.storage.coach import CoachRepository
from chesscoach.ui.course_center import CourseLibraryDialog, CoursePlayerDialog


def catalog() -> CourseCatalog:
    return CourseCatalog.from_data(
        {
            "schema_version": 1,
            "courses": [
                {
                    "id": "demo",
                    "version": 1,
                    "title": "Demo",
                    "description": "Practice",
                    "level_min": 600,
                    "level_max": 1400,
                    "side": "white",
                    "estimated_minutes": 5,
                    "modules": [
                        {"id": "m1", "title": "Start", "summary": "", "exercise_ids": ["e1"]}
                    ],
                    "exercises": [
                        {
                            "id": "e1",
                            "module_id": "m1",
                            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                            "learner_color": "white",
                            "line": ["e2e4", "e7e5"],
                            "prompt": "Play the center",
                            "hints": ["Use a central pawn"],
                        }
                    ],
                }
            ],
        }
    )


def test_course_library_filters_and_player_starts(app: QApplication, tmp_path: Path) -> None:
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    library = CourseLibraryDialog(catalog(), repository)
    assert library.list.count() == 1
    library.query.setText("missing")
    assert library.list.count() == 0
    library.query.setText("demo")
    assert library.list.count() == 1
    player = CoursePlayerDialog(catalog().courses[0], repository)
    assert player.status.text().startswith("Your move")
    player.close()
    library.close()
