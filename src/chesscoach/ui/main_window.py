"""Local two-player chess window."""

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chesscoach.chess.game import Game
from chesscoach.chess.pgn import export_pgn
from chesscoach.ui.chess_board import ChessBoard
from chesscoach.ui.move_history import MoveHistory


class MainWindow(QMainWindow):
    def __init__(self, game: Game | None = None) -> None:
        super().__init__()
        self.game = game if game is not None else Game()
        self.setWindowTitle("Chess Coach — Local game")
        self.resize(900, 650)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        self.board = ChessBoard(self.game)
        layout.addWidget(self.board, 3)
        sidebar = QVBoxLayout()
        layout.addLayout(sidebar, 1)
        title = QLabel("Chess Coach")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        sidebar.addWidget(title)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        sidebar.addWidget(self.status_label)
        help_text = QLabel("Local two-player game.\nSelect a piece, then its destination.")
        help_text.setWordWrap(True)
        sidebar.addWidget(help_text)
        self.history = MoveHistory()
        sidebar.addWidget(self.history, 1)
        self.new_game_button = QPushButton("New Game")
        self.undo_button = QPushButton("Undo")
        self.claim_draw_button = QPushButton("Claim Draw")
        self.copy_pgn_button = QPushButton("Copy PGN")
        for button in (
            self.new_game_button,
            self.undo_button,
            self.claim_draw_button,
            self.copy_pgn_button,
        ):
            sidebar.addWidget(button)
        self.new_game_button.clicked.connect(self.new_game)
        self.undo_button.clicked.connect(self.undo)
        self.claim_draw_button.clicked.connect(self.claim_draw)
        self.copy_pgn_button.clicked.connect(self.copy_pgn)
        self.board.game_changed.connect(self.refresh)
        self.board.message.connect(self.statusBar().showMessage)
        self.refresh()

    def refresh(self) -> None:
        status = self.game.status()
        self.status_label.setText(status.message)
        self.history.set_moves(self.game.history())
        self.undo_button.setEnabled(self.game.can_undo)
        self.claim_draw_button.setEnabled(status.can_claim_draw)
        self.board.refresh()

    def new_game(self) -> None:
        self.game.reset()
        self.board.clear_selection()
        self.statusBar().clearMessage()
        self.refresh()

    def undo(self) -> None:
        self.game.undo()
        self.board.clear_selection()
        self.statusBar().clearMessage()
        self.refresh()

    def claim_draw(self) -> None:
        if self.game.claim_draw():
            self.board.clear_selection()
            self.statusBar().clearMessage()
            self.refresh()

    def copy_pgn(self) -> None:
        QApplication.clipboard().setText(export_pgn(self.game))
        self.statusBar().showMessage("PGN copied to clipboard.", 4000)
