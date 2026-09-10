"""Lightweight clickable whole-game evaluation graph."""

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from chesscoach.coach.models import MoveAnalysis
from chesscoach.coach.scoring import white_win_probability


class EvaluationGraph(QWidget):
    index_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values: tuple[float, ...] = (0.5,)
        self.critical: frozenset[int] = frozenset()
        self.selected = 0
        self.setMinimumHeight(90)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Whole-game evaluation graph")
        self.setAccessibleDescription(
            "Use Left and Right to move through plies. Home and End jump to the game boundaries. "
            "Red diamond markers identify critical moves."
        )
        self.setToolTip("Click the graph to jump to a move. Higher positions favor White.")

    def set_moves(self, moves: tuple[MoveAnalysis, ...], critical: tuple[int, ...]) -> None:
        self.values = (0.5,) + tuple(white_win_probability(move.played_score) for move in moves)
        self.critical = frozenset(critical)
        self.selected = min(self.selected, len(moves))
        self.update()

    def set_selected(self, index: int) -> None:
        self.selected = max(0, min(index, len(self.values) - 1))
        self.update()

    def index_at_x(self, x: float) -> int:
        if len(self.values) <= 1 or self.width() <= 1:
            return 0
        return round(
            max(0.0, min(x, self.width() - 1)) / (self.width() - 1) * (len(self.values) - 1)
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.index_selected.emit(self.index_at_x(event.position().x()))
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self.index_selected.emit(max(0, self.selected - 1))
            event.accept()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self.index_selected.emit(min(len(self.values) - 1, self.selected + 1))
            event.accept()
        elif key == Qt.Key.Key_Home:
            self.index_selected.emit(0)
            event.accept()
        elif key == Qt.Key.Key_End:
            self.index_selected.emit(len(self.values) - 1)
            event.accept()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bounds = self.rect().adjusted(3, 3, -3, -3)
        painter.fillRect(bounds, QColor("#f5f3ef"))
        middle = bounds.center().y()
        painter.setPen(QPen(QColor("#aaa6a0"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(bounds.left(), middle, bounds.right(), middle)
        if len(self.values) < 2:
            return
        points = [
            QPointF(
                bounds.left() + index * bounds.width() / (len(self.values) - 1),
                bounds.bottom() - value * bounds.height(),
            )
            for index, value in enumerate(self.values)
        ]
        painter.setPen(QPen(QColor("#344f75"), 2))
        painter.drawPolyline(QPolygonF(points))
        for index in self.critical:
            if 0 < index < len(points):
                painter.setBrush(QColor("#c83f49"))
                painter.setPen(QPen(QColor("#7f1d2d"), 1))
                point = points[index]
                painter.drawPolygon(
                    QPolygonF(
                        (
                            QPointF(point.x(), point.y() - 5),
                            QPointF(point.x() + 5, point.y()),
                            QPointF(point.x(), point.y() + 5),
                            QPointF(point.x() - 5, point.y()),
                        )
                    )
                )
        selected = points[self.selected]
        painter.setBrush(QColor("#7b2f8e"))
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawEllipse(selected, 5, 5)
