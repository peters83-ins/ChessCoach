"""Small modal browser for locally saved matches."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
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
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Load Saved Game")
        self.resize(650, 360)
        layout = QVBoxLayout(self)
        location = QLabel(f"Saved games: {storage_path}")
        location.setWordWrap(True)
        location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(location)
        self.table = QTableWidget(len(games), 5)
        self.table.setHorizontalHeaderLabels(["Saved", "Player", "Bot", "Result", "Moves"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        for row, game in enumerate(games):
            values = (
                game.saved_at,
                game.player_color.title(),
                str(game.bot_elo),
                game.result,
                str(game.move_count),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, game.id)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        if games:
            self.table.selectRow(0)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel
        )
        self.open_button = buttons.button(QDialogButtonBox.StandardButton.Open)
        self.open_button.setText("Load for Analysis")
        self.open_button.setEnabled(bool(games))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.table.doubleClicked.connect(self.accept)
        layout.addWidget(buttons)

    def selected_game_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return str(item.data(Qt.ItemDataRole.UserRole)) if item else None
