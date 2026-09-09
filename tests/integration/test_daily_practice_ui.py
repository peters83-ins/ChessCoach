from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.courses.catalog import CourseCatalog
from chesscoach.storage.coach import CoachRepository
from chesscoach.ui.learning_center import PracticeQueueDialog


def test_daily_queue_includes_due_course_decisions(app: QApplication, tmp_path: Path) -> None:
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    catalog = CourseCatalog.built_in()
    repository.enroll_course(catalog.courses[0])
    queue = PracticeQueueDialog(repository, catalog=catalog)
    assert queue.table.rowCount() == 10
    assert queue.progress.text().startswith("Due today: 0 · Daily session: 10/10")
    assert queue.table.item(0, 0).text() == "Course"
    queue.close()
