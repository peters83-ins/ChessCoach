from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.courses.catalog import CourseCatalog
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.learning_home import LearningHomeDialog


def test_learning_home_empty_state_and_course_action(app: QApplication, tmp_path: Path) -> None:
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    database = GameDatabase(tmp_path / "games.sqlite3")
    catalog = CourseCatalog.built_in()
    dialog = LearningHomeDialog(repository, catalog, database)
    assert "opening course" in dialog.recommendation.text()
    assert dialog.continue_course.isEnabled()
    chosen: list[str] = []
    dialog.action_requested.connect(chosen.append)
    dialog.continue_course.click()
    assert chosen == ["course:italian-game-white"]
    assert "Resume" in dialog.continue_course.toolTip()


def test_learning_home_routes_to_first_due_course_decision(
    app: QApplication, tmp_path: Path
) -> None:
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    database = GameDatabase(tmp_path / "games.sqlite3")
    catalog = CourseCatalog.built_in()
    course = catalog.courses[0]
    repository.enroll_course(course)
    dialog = LearningHomeDialog(repository, catalog, database)
    chosen: list[str] = []
    dialog.action_requested.connect(chosen.append)
    dialog.continue_course.click()
    assert chosen == [f"course:{course.id}:{course.exercises[0].id}"]
