from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow
from chesscoach.ui.saved_games import SavedGamesDialog


def test_saved_game_library_reports_filter_count(app: QApplication, tmp_path: Path) -> None:
    dialog = SavedGamesDialog((), str(GameDatabase(tmp_path / "games.sqlite3").path))
    assert dialog.filter_summary.text() == "Showing 0 of 0 saved games"
    assert not dialog.export_all_button.isEnabled()
    dialog.close()


def test_main_window_imports_multiple_pgn_games(app: QApplication, tmp_path: Path) -> None:
    source = tmp_path / "batch.pgn"
    source.write_text('[Result "*"]\n\n1. e4 *\n\n[Result "*"]\n\n1. d4 *', encoding="utf-8")
    database = GameDatabase(tmp_path / "games.sqlite3")
    window = MainWindow(database=database)
    with patch(
        "chesscoach.ui.main_window.QFileDialog.getOpenFileName",
        return_value=(str(source), "PGN (*.pgn *.txt)"),
    ):
        window.import_pgn()
    assert len(database.list_games()) == 2
    assert "Imported 2 game(s)" in window.statusBar().currentMessage()
    window.close()
