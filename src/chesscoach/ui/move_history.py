"""Read-only SAN move list grouped by full move number."""

import chess
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from chesscoach.chess.game import PlayedMove


class MoveHistory(QTableWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels(["Move", "White", "Black"])
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAccessibleName("Move history in standard algebraic notation")

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
