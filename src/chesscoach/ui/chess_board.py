"""Clickable board with coordinates and explicit promotion selection."""

import chess
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGridLayout, QInputDialog, QLabel, QPushButton, QSizePolicy, QWidget

from chesscoach.chess.game import Game

PROMOTIONS = {
    "Queen": chess.QUEEN,
    "Rook": chess.ROOK,
    "Bishop": chess.BISHOP,
    "Knight": chess.KNIGHT,
}


class ChessBoard(QWidget):
    game_changed = Signal()
    message = Signal(str)

    def __init__(self, game: Game, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.game = game
        self.selected_square: chess.Square | None = None
        self.squares: dict[chess.Square, QPushButton] = {}
        layout = QGridLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        font = QFont("Segoe UI Symbol", 32)
        font.setFamilies(["Segoe UI Symbol", "DejaVu Sans", "Arial Unicode MS"])
        for row in range(8):
            rank_label = QLabel(str(8 - row))
            rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rank_label.setFixedWidth(24)
            layout.addWidget(rank_label, row, 0)
            for file in range(8):
                square = chess.square(file, 7 - row)
                button = QPushButton()
                button.setFont(font)
                button.setMinimumSize(52, 52)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                button.clicked.connect(lambda checked=False, s=square: self.select_square(s))
                self.squares[square] = button
                layout.addWidget(button, row, file + 1)
            layout.setRowStretch(row, 1)
        for file in range(8):
            label = QLabel(chess.FILE_NAMES[file])
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(24)
            layout.addWidget(label, 8, file + 1)
            layout.setColumnStretch(file + 1, 1)
        self.refresh()

    def clear_selection(self) -> None:
        self.selected_square = None
        self.refresh()

    def refresh(self) -> None:
        destinations = (
            {m.to_square for m in self.game.legal_moves_from(self.selected_square)}
            if self.selected_square is not None
            else set()
        )
        for square, button in self.squares.items():
            piece = self.game.piece_at(square)
            button.setText(piece.unicode_symbol() if piece else "")
            name = chess.square_name(square)
            description = (
                f"{'White' if piece.color else 'Black'} {chess.piece_name(piece.piece_type)}"
                if piece
                else "empty"
            )
            button.setAccessibleName(f"{name}: {description}")
            button.setToolTip(f"{name}: {description}")
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            background = "#f0d9b5" if light else "#b58863"
            border = "transparent"
            if square == self.selected_square:
                background, border = "#f6dd65", "#806500"
            elif square in destinations:
                border = "#246b45"
            button.setStyleSheet(
                f"QPushButton {{ background: {background}; color: #151515;"
                f" border: 3px solid {border}; border-radius: 0; padding: 0; }}"
                "QPushButton:focus { border: 3px solid #305da8; }"
            )

    def select_square(self, square: chess.Square) -> None:
        if self.game.status().game_over:
            self.message.emit("Game over. Start a new game or undo a move.")
            return
        piece = self.game.piece_at(square)
        if square == self.selected_square:
            self.clear_selection()
            return
        if piece and piece.color == self.game.turn:
            self.selected_square = square
            self.refresh()
            self.message.emit("Choose a highlighted destination.")
            return
        if self.selected_square is None:
            self.message.emit("Select a piece belonging to the side to move.")
            return
        candidates = [
            move
            for move in self.game.legal_moves_from(self.selected_square)
            if move.to_square == square
        ]
        if not candidates:
            self.message.emit("Illegal move. Choose a highlighted destination or another piece.")
            return
        move = candidates[0]
        if move.promotion:
            promotion = self.choose_promotion()
            if promotion is None:
                return
            move = chess.Move(self.selected_square, square, promotion)
        if self.game.attempt_move(move):
            self.clear_selection()
            self.message.emit("")
            self.game_changed.emit()

    def choose_promotion(self) -> chess.PieceType | None:
        choice, accepted = QInputDialog.getItem(
            self, "Promote pawn", "Choose a piece:", list(PROMOTIONS), 0, False
        )
        return PROMOTIONS[choice] if accepted else None
