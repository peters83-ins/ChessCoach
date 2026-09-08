"""Render the filled SVG pieces bundled with python-chess, cached as Qt icons."""

from functools import lru_cache

import chess
import chess.svg
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


@lru_cache(maxsize=12)
def piece_icon(piece_type: chess.PieceType, color: chess.Color) -> QIcon:
    svg = chess.svg.piece(chess.Piece(piece_type, color))
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    icon = QIcon(pixmap)
    # Board locks must not gray out the pieces during an engine turn.
    icon.addPixmap(pixmap, QIcon.Mode.Disabled)
    return icon
