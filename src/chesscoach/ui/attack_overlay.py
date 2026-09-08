"""Mouse-transparent threat arrows laid over the board's existing controls."""

import math
from collections.abc import Callable

import chess
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QPushButton, QWidget

from chesscoach.chess.attacks import attack_pairs


class AttackOverlay(QWidget):
    def __init__(
        self,
        parent: QWidget,
        squares: dict[chess.Square, QPushButton],
        position: Callable[[], chess.Board],
    ) -> None:
        super().__init__(parent)
        self.squares, self.position = squares, position
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.hide()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(205, 35, 45, 195)
        painter.setPen(QPen(color, 3))
        painter.setBrush(color)
        for source, target in attack_pairs(self.position()):
            start = QPointF(self.squares[source].geometry().center())
            end = QPointF(self.squares[target].geometry().center())
            delta = end - start
            length = math.hypot(delta.x(), delta.y())
            if length == 0:
                continue
            unit = delta / length
            # Shorten both ends to keep the piece centers visible.
            start += unit * 12
            end -= unit * 12
            painter.drawLine(start, end)
            base = end - unit * 11
            normal = QPointF(-unit.y(), unit.x()) * 5
            painter.drawPolygon(QPolygonF([end, base + normal, base - normal]))
        painter.end()
