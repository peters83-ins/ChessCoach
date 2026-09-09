"""Clickable board with coordinates and explicit promotion selection."""

import chess
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QResizeEvent
from PySide6.QtWidgets import QGridLayout, QInputDialog, QLabel, QPushButton, QSizePolicy, QWidget

from chesscoach.chess.game import Game
from chesscoach.ui.attack_overlay import AttackOverlay
from chesscoach.ui.piece_assets import piece_icon

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
        self.orientation = chess.WHITE
        self.input_allowed = True
        self.preview_only = False
        self.input_message = "Wait for the computer to move."
        self.played_highlight: chess.Move | None = None
        self.best_highlight: chess.Move | None = None
        self.squares: dict[chess.Square, QPushButton] = {}
        layout = QGridLayout(self)
        self.board_layout = layout
        self.rank_labels: list[QLabel] = []
        self.file_labels: list[QLabel] = []
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        for row in range(8):
            rank_label = QLabel(str(8 - row))
            self.rank_labels.append(rank_label)
            rank_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rank_label.setFixedWidth(24)
            layout.addWidget(rank_label, row, 0)
            for file in range(8):
                square = chess.square(file, 7 - row)
                button = QPushButton()
                button.setIconSize(QSize(46, 46))
                button.setMinimumSize(52, 52)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                button.clicked.connect(lambda checked=False, s=square: self.select_square(s))
                self.squares[square] = button
                layout.addWidget(button, row, file + 1)
            layout.setRowStretch(row, 1)
        for file in range(8):
            label = QLabel(chess.FILE_NAMES[file])
            self.file_labels.append(label)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedHeight(24)
            layout.addWidget(label, 8, file + 1)
            layout.setColumnStretch(file + 1, 1)
        self.overlay = AttackOverlay(self, self.squares, lambda: self.game.position)
        self.classification_badge = QLabel(self)
        self.classification_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.classification_badge.setFixedSize(88, 30)
        self.classification_badge.hide()
        self.refresh()

    def set_orientation(self, color: chess.Color) -> None:
        self.orientation = color
        for square, button in self.squares.items():
            row = 7 - chess.square_rank(square) if color else chess.square_rank(square)
            column = chess.square_file(square) if color else 7 - chess.square_file(square)
            self.board_layout.addWidget(button, row, column + 1)
        for index in range(8):
            self.rank_labels[index].setText(str(8 - index if color else index + 1))
            self.file_labels[index].setText(chess.FILE_NAMES[index if color else 7 - index])
        self.clear_selection()

    def set_attacks_visible(self, visible: bool) -> None:
        self.overlay.setGeometry(self.rect())
        self.classification_badge.move(max(0, self.width() - 94), 6)
        self.classification_badge.raise_()
        self.overlay.setVisible(visible)
        self.overlay.raise_()
        self.overlay.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())

    def clear_selection(self) -> None:
        self.selected_square = None
        self.refresh()

    def set_review_moves(self, played: chess.Move | None, best: chess.Move | None) -> None:
        self.played_highlight = played
        self.best_highlight = best
        self.refresh()

    def set_classification(self, text: str, color: str = "#555555") -> None:
        self.classification_badge.move(max(0, self.width() - 94), 6)
        self.classification_badge.setText(text)
        self.classification_badge.setStyleSheet(
            f"background: {color}; color: white; font-weight: bold; border-radius: 5px;"
        )
        self.classification_badge.setAccessibleName(f"Move classification: {text}")
        self.classification_badge.setVisible(bool(text))
        self.classification_badge.raise_()

    def refresh(self) -> None:
        destinations = (
            {m.to_square for m in self.game.legal_moves_from(self.selected_square)}
            if self.selected_square is not None
            else set()
        )
        for square, button in self.squares.items():
            piece = self.game.piece_at(square)
            button.setIcon(piece_icon(piece.piece_type, piece.color) if piece else QIcon())
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
            if self.played_highlight and square in (
                self.played_highlight.from_square,
                self.played_highlight.to_square,
            ):
                background = "#72a7d8"
            if square == self.selected_square:
                background, border = "#f6dd65", "#806500"
            elif self.best_highlight and square in (
                self.best_highlight.from_square,
                self.best_highlight.to_square,
            ):
                border = "#9b35ad"
            elif square in destinations:
                border = "#246b45"
            button.setStyleSheet(
                f"QPushButton {{ background: {background}; color: #151515;"
                f" border: 3px solid {border}; border-radius: 0; padding: 0; }}"
                "QPushButton:focus { border: 3px solid #305da8; }"
            )
        self.overlay.raise_()
        self.overlay.update()

    def select_square(self, square: chess.Square) -> None:
        if not self.input_allowed and not self.preview_only:
            self.message.emit(self.input_message)
            return
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
            self.message.emit(
                self.input_message if self.preview_only else "Choose a highlighted destination."
            )
            return
        if self.preview_only:
            self.message.emit(self.input_message)
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
