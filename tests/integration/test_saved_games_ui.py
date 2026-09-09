from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.storage.database import GameDatabase
from chesscoach.ui.saved_games import SavedGamesDialog


def test_saved_game_library_reports_filter_count(app: QApplication, tmp_path: Path) -> None:
    dialog = SavedGamesDialog((), str(GameDatabase(tmp_path / "games.sqlite3").path))
    assert dialog.filter_summary.text() == "Showing 0 of 0 saved games"
    dialog.close()
