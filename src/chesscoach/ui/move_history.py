"""Read-only SAN move list grouped by full move number."""

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from chesscoach.chess.game import PlayedMove
from chesscoach.coach.models import MoveAnalysis, MoveClassification

BADGES = {
    MoveClassification.BEST: ("✓", "#4d8f55"),
    MoveClassification.EXCELLENT: ("★", "#3d7f88"),
    MoveClassification.GOOD: ("•", "#77915b"),
    MoveClassification.INACCURACY: ("?!", "#c59b35"),
    MoveClassification.MISTAKE: ("?", "#d17336"),
    MoveClassification.BLUNDER: ("??", "#c8464d"),
}


class MoveHistory(QTableWidget):
    move_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["Move", "White", "Black"])
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAccessibleName("Move history in standard algebraic notation")
        self.cellClicked.connect(self._cell_clicked)

    def set_moves(self, moves: tuple[PlayedMove, ...]) -> None:
        self.setRowCount(0)
        previous_number = None
        for move in moves:
            if move.number != previous_number:
                row = self.rowCount()
                self.insertRow(row)
                self.setItem(row, 0, QTableWidgetItem(str(move.number)))
                previous_number = move.number
            column = 1 if move.color == chess.WHITE else 2
            self.setItem(self.rowCount() - 1, column, QTableWidgetItem(move.san))
        self.scrollToBottom()

    def set_classifications(self, moves: tuple[MoveAnalysis, ...]) -> None:
        for move in moves:
            row = (move.ply - 1) // 2
            column = 1 if move.ply % 2 else 2
            item = self.item(row, column)
            if item is None:
                continue
            badge, color = BADGES[move.classification]
            if not item.data(Qt.ItemDataRole.UserRole):
                item.setText(f"{item.text()}  {badge}")
            item.setData(Qt.ItemDataRole.UserRole, move.classification.value)
            item.setBackground(QColor(color))
            item.setForeground(QColor("#ffffff"))
            item.setToolTip(f"{move.classification.value.title()} · {move.accuracy:.1f}%")

    def _cell_clicked(self, row: int, column: int) -> None:
        if column == 1 and self.item(row, column) is not None:
            self.move_selected.emit(row * 2 + 1)
        elif column == 2 and self.item(row, column) is not None:
            self.move_selected.emit(row * 2 + 2)
