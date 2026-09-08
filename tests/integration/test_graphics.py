import chess
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from chesscoach.chess.game import Game
from chesscoach.ui.chess_board import ChessBoard
from chesscoach.ui.piece_assets import piece_icon


def test_filled_piece_colors(app: QApplication) -> None:
    white = piece_icon(chess.PAWN, chess.WHITE).pixmap(128, 128).toImage()
    black = piece_icon(chess.PAWN, chess.BLACK).pixmap(128, 128).toImage()
    # Interior of the pawn's base is opaque white/black, independent of square color.
    assert white.pixelColor(64, 100).getRgb() == (255, 255, 255, 255)
    assert black.pixelColor(64, 100).getRgb() == (0, 0, 0, 255)


def test_orientation_overlay_and_click_through(app: QApplication) -> None:
    game = Game("7k/8/8/3p4/4P3/8/8/K7 w - - 0 1")
    widget = ChessBoard(game)
    widget.resize(550, 550)
    widget.show()
    app.processEvents()
    widget.set_orientation(chess.BLACK)
    app.processEvents()
    assert widget.squares[chess.A8].y() > widget.squares[chess.A1].y()
    assert widget.squares[chess.A1].x() > widget.squares[chess.H1].x()
    assert widget.rank_labels[0].text() == "1"
    assert widget.file_labels[0].text() == "h"
    before = widget.grab().toImage()
    widget.set_attacks_visible(True)
    app.processEvents()
    assert widget.overlay.isVisible()
    assert widget.grab().toImage() != before
    # Send to the actual child under the pointer to verify overlay transparency.
    for square in (chess.E4, chess.D5):
        button = widget.squares[square]
        assert widget.childAt(button.geometry().center()) is button
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    assert game.history()[-1].san == "exd5"
    widget.set_attacks_visible(False)
    assert not widget.overlay.isVisible()
    widget.close()
