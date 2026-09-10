"""Offline self-analysis board for exploring legal positions without a match."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chesscoach.chess.game import Game
from chesscoach.ui.chess_board import ChessBoard


class AnalysisSandboxDialog(QDialog):
    """Play through a position locally; engine analysis can be added independently."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Self-analysis sandbox")
        self.resize(700, 620)
        self.game = Game()
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("FEN"))
        self.fen = QLineEdit(self.game.fen)
        self.fen.setAccessibleName("Sandbox position FEN")
        controls.addWidget(self.fen, 1)
        self.load_button = QPushButton("Load position")
        self.load_button.setAccessibleName("Load sandbox FEN")
        controls.addWidget(self.load_button)
        layout.addLayout(controls)
        self.board = ChessBoard(self.game)
        self.board.setAccessibleName("Self-analysis chess board")
        layout.addWidget(self.board, 1)
        self.status = QLabel(
            "Explore this position locally. Stockfish analysis can be requested from here later."
        )
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.copy_fen = QPushButton("Copy current FEN")
        self.copy_fen.setAccessibleName("Copy sandbox FEN")
        layout.addWidget(self.copy_fen)
        self.load_button.clicked.connect(self.load_position)
        self.board.game_changed.connect(self.position_changed)
        self.copy_fen.clicked.connect(self.copy_position)

    def load_position(self) -> None:
        try:
            self.game = Game(self.fen.text().strip())
        except ValueError as error:
            self.status.setText(f"Invalid position: {error}")
            return
        self.board.game = self.game
        self.board.clear_selection()
        self.status.setText("Position loaded. Select a piece, then a legal destination.")

    def position_changed(self) -> None:
        self.fen.setText(self.game.fen)
        self.status.setText(self.game.status().message)

    def copy_position(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.game.fen)
        self.status.setText("Current FEN copied.")
