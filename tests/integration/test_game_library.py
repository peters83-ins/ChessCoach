from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.storage.database import SavedGameSummary
from chesscoach.ui.saved_games import SavedGamesDialog


def games() -> tuple[SavedGameSummary, ...]:
    return (
        SavedGameSummary("a", "2026-01-02", "white", 1000, "1-0", 20, "Ruy Lopez", True, 2),
        SavedGameSummary("b", "2026-01-01", "black", 1200, "0-1", 30, "Sicilian Defense"),
    )


def test_game_library_filters_and_sorts(app: QApplication) -> None:
    dialog = SavedGamesDialog(games(), "games.sqlite3")
    assert dialog.table.rowCount() == 2
    dialog.search.setText("sicilian")
    assert dialog.table.rowCount() == 1
    assert dialog.selected_game_id() == "b"
    dialog.search.clear()
    dialog.analysis_filter.setCurrentText("Analyzed")
    assert dialog.table.rowCount() == 1
    assert dialog.selected_game_id() == "a"
    dialog.analysis_filter.setCurrentText("Any analysis")
    dialog.sort_order.setCurrentText("Most moves")
    assert dialog.selected_game_id() == "b"


def test_game_library_export_callback(app: QApplication, tmp_path: Path, monkeypatch) -> None:
    exported: list[tuple[str, Path]] = []
    target = tmp_path / "game.pgn"
    dialog = SavedGamesDialog(
        games(),
        "games.sqlite3",
        export_game=lambda game_id, path: not exported.append((game_id, path)),
    )
    monkeypatch.setattr(
        "chesscoach.ui.saved_games.QFileDialog.getSaveFileName",
        lambda *args: (str(target), "PGN"),
    )
    dialog.export_button.click()
    assert exported == [("a", target)]
