from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow
from chesscoach.ui.theme import MODERN_STYLESHEET


def test_modern_theme_is_applied_to_primary_actions(app: QApplication, tmp_path: Path) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"))
    assert MODERN_STYLESHEET in window.styleSheet()
    assert window.new_game_button.objectName() == "primaryAction"
    assert window.save_button.objectName() == "primaryAction"
    assert window.setup.start_button.objectName() == "primaryAction"
    window.close()
