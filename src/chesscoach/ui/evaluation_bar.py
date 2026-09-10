"""Compact vertical display of a Stockfish score."""

import math

import chess
import chess.engine
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget


def white_score_fraction(score: chess.engine.PovScore) -> float:
    """Map a White-perspective engine score to the bar's White share."""
    white_score = score.white()
    mate = white_score.mate()
    if mate is not None:
        return 0.98 if mate > 0 else 0.02
    centipawns = white_score.score() or 0
    return 0.5 + 0.48 * math.tanh(centipawns / 600)


class EvaluationBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.white_fraction = 0.5
        self.white_at_bottom = True
        self.display_text = "—"
        self.setFixedWidth(34)
        self.setMinimumHeight(160)
        self.setToolTip("Current Stockfish evaluation. Positive values favor White.")
        self._update_accessibility()

    def sizeHint(self) -> QSize:
        return QSize(34, 520)

    def clear(self) -> None:
        self.white_fraction = 0.5
        self.display_text = "—"
        self._update_accessibility()
        self.update()

    def set_orientation(self, white_at_bottom: bool) -> None:
        self.white_at_bottom = white_at_bottom
        self.update()

    def set_score(self, score: chess.engine.PovScore) -> None:
        white_score = score.white()
        mate = white_score.mate()
        centipawns = white_score.score()
        self.white_fraction = white_score_fraction(score)
        self.display_text = f"M{mate:+d}" if mate is not None else f"{(centipawns or 0) / 100:+.1f}"
        self._update_accessibility()
        self.update()

    def set_result(self, winner: chess.Color | None) -> None:
        self.white_fraction = (
            0.98 if winner == chess.WHITE else 0.02 if winner == chess.BLACK else 0.5
        )
        self.display_text = (
            "1-0" if winner == chess.WHITE else "0-1" if winner == chess.BLACK else "½"
        )
        self._update_accessibility()
        self.update()

    def _update_accessibility(self) -> None:
        self.setAccessibleName(f"Board evaluation: {self.display_text}")
        self.setAccessibleDescription(
            "White share of the current Stockfish evaluation; the dark section favors Black."
        )

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        bounds = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(bounds, QColor("#262421"))
        white_height = round(bounds.height() * self.white_fraction)
        if self.white_at_bottom:
            white_rect = QRect(
                bounds.left(), bounds.bottom() - white_height + 1, bounds.width(), white_height
            )
        else:
            white_rect = QRect(bounds.left(), bounds.top(), bounds.width(), white_height)
        painter.fillRect(white_rect, QColor("#f2f2f2"))
        painter.setPen(QPen(QColor("#66635f"), 1))
        painter.drawRect(bounds)

        font = QFont(self.font())
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        white_winning = self.white_fraction >= 0.5
        painter.setPen(QColor("#181715") if white_winning else QColor("#ffffff"))
        text_height = 22
        if white_winning == self.white_at_bottom:
            text_rect = QRect(
                bounds.left(), bounds.bottom() - text_height + 1, bounds.width(), text_height
            )
        else:
            text_rect = QRect(bounds.left(), bounds.top(), bounds.width(), text_height)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.display_text)
