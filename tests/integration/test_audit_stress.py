from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.engine.worker import EngineRunner
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow


class IdleEngine(EngineRunner):
    def search(self, *args: object, **kwargs: object) -> None:
        self.cancel()


def test_rapid_destination_switching_is_repeatable(
    app: QApplication, tmp_path: Path
) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"), runner=IdleEngine())
    open_destinations = (
        window.open_learning_home,
        window.open_courses,
        window.open_lessons,
        window.open_practice,
        window.open_insights,
    )
    for _ in range(3):
        for open_destination in open_destinations:
            open_destination()
            app.processEvents()
    assert set(window.destination_dialogs) >= {
        "learn",
        "courses",
        "practice",
        "insights",
    }
    window.close()
