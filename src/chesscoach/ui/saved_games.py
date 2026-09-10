"""Filterable local game library with safe export and deletion."""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chesscoach.storage.database import SavedGameSummary


class SavedGamesDialog(QDialog):
    def __init__(
        self,
        games: tuple[SavedGameSummary, ...],
        storage_path: str,
        parent: QWidget | None = None,
        *,
        delete_game: Callable[[str], bool] | None = None,
        export_game: Callable[[str, Path], bool] | None = None,
    ) -> None:
        super().__init__(parent)
        self.games = games
        self.delete_game = delete_game
        self.export_game = export_game
        self.setWindowTitle("Games")
        self.resize(980, 520)
        layout = QVBoxLayout(self)
        location = QLabel(f"Saved games: {storage_path}")
        location.setWordWrap(True)
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(location)
        filters = QFormLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search opening, result, date, color, or difficulty")
        filters.addRow("Search", self.search)
        row = QHBoxLayout()
        self.color_filter = QComboBox()
        self.color_filter.addItems(("Any color", "White", "Black"))
        self.result_filter = QComboBox()
        self.result_filter.addItems(("Any result", "1-0", "0-1", "1/2-1/2", "*"))
        self.analysis_filter = QComboBox()
        self.analysis_filter.addItems(("Any analysis", "Analyzed", "Not analyzed"))
        self.sort_order = QComboBox()
        self.sort_order.addItems(("Newest", "Oldest", "Most moves", "Highest difficulty"))
        for widget in (
            self.color_filter,
            self.result_filter,
            self.analysis_filter,
            self.sort_order,
        ):
            row.addWidget(widget)
        filters.addRow("Filter and sort", row)
        layout.addLayout(filters)
        self.filter_summary = QLabel()
        layout.addWidget(self.filter_summary)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ("Saved", "Player", "Bot", "Result", "Moves", "Opening", "Analysis", "Practice")
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.setAccessibleName("Saved game library")
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.export_button = QPushButton("Export PGN…")
        self.delete_button = QPushButton("Delete…")
        actions.addWidget(self.export_button)
        actions.addWidget(self.delete_button)
        layout.addLayout(actions)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel
        )
        self.open_button = buttons.button(QDialogButtonBox.StandardButton.Open)
        self.open_button.setText("Open Review")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.table.doubleClicked.connect(self.accept)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self.refresh)
        self.color_filter.currentIndexChanged.connect(self.refresh)
        self.result_filter.currentIndexChanged.connect(self.refresh)
        self.analysis_filter.currentIndexChanged.connect(self.refresh)
        self.sort_order.currentIndexChanged.connect(self.refresh)
        self.export_button.clicked.connect(self._export)
        self.delete_button.clicked.connect(self._delete)
        self.refresh()

    def refresh(self) -> None:
        query = self.search.text().strip().casefold()
        color = self.color_filter.currentText().casefold()
        result = self.result_filter.currentText()
        analysis = self.analysis_filter.currentText()
        games = [
            game
            for game in self.games
            if (color == "any color" or game.player_color == color)
            and (result == "Any result" or game.result == result)
            and (
                analysis == "Any analysis"
                or (analysis == "Analyzed" and game.analyzed)
                or (analysis == "Not analyzed" and not game.analyzed)
            )
            and (
                not query
                or query
                in " ".join(
                    (
                        game.saved_at,
                        game.player_color,
                        str(game.bot_elo),
                        game.result,
                        game.opening,
                    )
                ).casefold()
            )
        ]
        self.filter_summary.setText(f"Showing {len(games)} of {len(self.games)} saved games")
        sort_key = self.sort_order.currentText()
        if sort_key == "Oldest":
            games.sort(key=lambda game: game.saved_at)
        elif sort_key == "Most moves":
            games.sort(key=lambda game: (-game.move_count, game.saved_at))
        elif sort_key == "Highest difficulty":
            games.sort(key=lambda game: (-game.bot_elo, game.saved_at))
        else:
            games.sort(key=lambda game: game.saved_at, reverse=True)
        self.table.setRowCount(len(games))
        for row_index, game in enumerate(games):
            values = (
                game.saved_at,
                game.player_color.title(),
                str(game.bot_elo),
                game.result,
                str(game.move_count),
                game.opening,
                "Analyzed" if game.analyzed else "Pending",
                str(game.practice_count),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, game.id)
                self.table.setItem(row_index, column, item)
        self.table.resizeColumnsToContents()
        if games:
            self.table.selectRow(0)
        enabled = bool(games)
        self.open_button.setEnabled(enabled)
        self.export_button.setEnabled(enabled and self.export_game is not None)
        self.delete_button.setEnabled(enabled and self.delete_game is not None)
        self.open_button.setToolTip(
            "Open the selected saved game." if enabled else "No saved game matches the filters."
        )
        self.export_button.setToolTip(
            "Export the selected game as PGN."
            if self.export_button.isEnabled()
            else "Select a saved game before exporting."
        )
        self.delete_button.setToolTip(
            "Delete the selected saved game."
            if self.delete_button.isEnabled()
            else "Select a saved game before deleting."
        )

    def selected_game_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _export(self) -> None:
        game_id = self.selected_game_id()
        if game_id is None or self.export_game is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export PGN", "game.pgn", "PGN (*.pgn)")
        if path:
            self.export_game(game_id, Path(path))

    def _delete(self) -> None:
        game_id = self.selected_game_id()
        if game_id is None or self.delete_game is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete saved game?",
            "Delete this game and its analysis, feedback, and practice positions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.delete_game(game_id):
            self.games = tuple(game for game in self.games if game.id != game_id)
            self.refresh()
