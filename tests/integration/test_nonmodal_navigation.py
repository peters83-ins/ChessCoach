from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.engine.worker import EngineRunner
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow


class IdleEngine(EngineRunner):
    def search(self, *args: object, **kwargs: object) -> None:
        self.cancel()


def test_navigation_destinations_can_stay_open_and_switch(
    app: QApplication, tmp_path: Path
) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"), runner=IdleEngine())
    window.open_courses()
    first = window.destination_dialogs["courses"]
    window.open_courses()
    assert window.destination_dialogs["courses"] is first
    window.open_learning_home()
    assert set(window.destination_dialogs) >= {"courses", "learn"}
    window.close()
