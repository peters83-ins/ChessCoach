from collections.abc import Iterator
from unittest.mock import patch

import chess
import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog

from chesscoach.chess.game import Game
from chesscoach.main import main
from chesscoach.ui.main_window import MainWindow


@pytest.fixture
def window(app: QApplication) -> Iterator[MainWindow]:
    widget = MainWindow()
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    widget.deleteLater()
    app.processEvents()


def click(window: MainWindow, square: str) -> None:
    QTest.mouseClick(window.board.squares[chess.parse_square(square)], Qt.MouseButton.LeftButton)


def test_board_controls_and_history(window: MainWindow, app: QApplication) -> None:
    assert len(window.board.squares) == 64
    assert window.board.squares[chess.A8].y() < window.board.squares[chess.A1].y()
    assert window.board.squares[chess.A1].x() < window.board.squares[chess.H1].x()
    assert not window.undo_button.isEnabled()
    click(window, "e4")
    click(window, "e7")
    assert window.board.selected_square is None
    click(window, "e2")
    assert window.board.selected_square == chess.E2
    click(window, "e5")
    assert window.game.fen == chess.STARTING_FEN
    assert "Illegal" in window.statusBar().currentMessage()
    click(window, "e4")
    assert window.game.history()[0].san == "e4"
    assert window.status_label.text() == "Black to move"
    assert window.history.item(0, 1).text() == "e4"
    click(window, "e7")
    click(window, "e5")
    assert window.history.item(0, 2).text() == "e5"
    window.copy_pgn_button.click()
    assert "1. e4 e5 *" in app.clipboard().text()
    window.undo_button.click()
    assert len(window.game.history()) == 1
    assert window.history.item(0, 2) is None
    window.new_game_button.click()
    assert window.game.fen == chess.STARTING_FEN
    assert window.history.rowCount() == 0
    assert window.board.selected_square is None
    assert not window.undo_button.isEnabled()


def test_selection_toggle_and_switch(window: MainWindow) -> None:
    click(window, "e2")
    click(window, "d2")
    assert window.board.selected_square == chess.D2
    click(window, "d2")
    assert window.board.selected_square is None


@pytest.mark.parametrize("name", ["Queen", "Rook", "Bishop", "Knight"])
def test_promotion_dialog(window: MainWindow, name: str) -> None:
    # Keep a pawn to avoid an insufficient-material draw after underpromotion.
    game = Game("7k/P6p/8/8/8/8/8/7K w - - 0 1")
    window.game = game
    window.board.game = game
    window.refresh()
    with patch.object(QInputDialog, "getItem", return_value=(name, True)) as dialog:
        click(window, "a7")
        click(window, "a8")
    dialog.assert_called_once()
    assert chess.piece_name(game.piece_at(chess.A8).piece_type) == name.lower()
    assert window.history.rowCount() == 1
    assert window.board.selected_square is None


def test_promotion_cancel(window: MainWindow) -> None:
    game = Game("7k/P7/8/8/8/8/8/7K w - - 0 1")
    window.game = game
    window.board.game = game
    before = game.fen
    with patch.object(QInputDialog, "getItem", return_value=("", False)):
        click(window, "a7")
        click(window, "a8")
    assert game.fen == before
    assert window.board.selected_square == chess.A7


def test_game_over_and_recovery(window: MainWindow) -> None:
    for source, target in [("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")]:
        click(window, source)
        click(window, target)
    assert "Black wins" in window.status_label.text()
    click(window, "e2")
    assert "Game over" in window.statusBar().currentMessage()
    window.undo_button.click()
    assert not window.game.status().game_over
    assert window.statusBar().currentMessage() == ""


def test_claim_draw_button(window: MainWindow) -> None:
    for _ in range(2):
        for source, target in [("g1", "f3"), ("g8", "f6"), ("f3", "g1"), ("f6", "g8")]:
            click(window, source)
            click(window, target)
    assert window.claim_draw_button.isEnabled()
    window.claim_draw_button.click()
    assert window.status_label.text() == "Draw claimed"
    assert not window.claim_draw_button.isEnabled()
    window.undo_button.click()
    assert not window.game.status().game_over


def test_launch_entry_point(app: QApplication) -> None:
    # Reuse the test QApplication and exercise the actual event-loop entry point.
    with patch("chesscoach.main.QApplication", return_value=app):
        QTimer.singleShot(50, app.quit)
        assert main() == 0
