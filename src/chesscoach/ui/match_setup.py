"""Match choices; engine binaries are selected locally, never bundled."""

from pathlib import Path

import chess
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from chesscoach.config import Settings
from chesscoach.engine.stockfish import DIFFICULTIES


class MatchSetup(QWidget):
    start_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.mode = QComboBox()
        self.mode.addItems(["Play Stockfish", "Local two-player"])
        self.color = QComboBox()
        self.color.addItem("White", chess.WHITE)
        self.color.addItem("Black", chess.BLACK)
        self.difficulty = QComboBox()
        for label, elo in DIFFICULTIES.items():
            self.difficulty.addItem(label, elo)
        self.engine_path = QLineEdit(Settings.from_environment(Path(".env")).stockfish_path)
        self.engine_path.setPlaceholderText("Stockfish executable or command")
        self.browse = QPushButton("Browse…")
        self.browse.clicked.connect(self.choose_engine)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.engine_path, 1)
        path_layout.addWidget(self.browse)
        self.start_button = QPushButton("Start Match")
        self.start_button.clicked.connect(self.start_requested.emit)
        layout.addRow("Mode", self.mode)
        layout.addRow("Your color", self.color)
        layout.addRow("Bot difficulty", self.difficulty)
        layout.addRow(path_layout)
        layout.addRow(self.start_button)
        self.mode.currentIndexChanged.connect(self.update_mode)

    def update_mode(self) -> None:
        bot = self.mode.currentIndex() == 0
        for widget in (self.color, self.difficulty, self.engine_path, self.browse):
            widget.setEnabled(bot)

    def choose_engine(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish executable")
        if path:
            self.engine_path.setText(path)
