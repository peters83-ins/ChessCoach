"""Move navigation and engine comparison details for a loaded game."""

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from chesscoach.coach.models import GameAnalysis
from chesscoach.ui.evaluation_graph import EvaluationGraph


class GameReview(QWidget):
    index_changed = Signal(int)
    show_line_requested = Signal()
    retry_requested = Signal()
    hint_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.key_moments: tuple[int, ...] = ()
        self.graph = EvaluationGraph()
        self.graph.index_selected.connect(self.index_changed.emit)
        layout.addWidget(self.graph)
        self.next_key_button = QPushButton("Next Key Moment")
        self.next_key_button.setAccessibleName("Go to next key moment")
        self.next_key_button.clicked.connect(self._next_key)
        self.next_key_button.setEnabled(False)
        layout.addWidget(self.next_key_button)
        controls = QGridLayout()
        self.start_button = QPushButton("|◀")
        self.previous_button = QPushButton("◀")
        self.next_button = QPushButton("▶")
        self.end_button = QPushButton("▶|")
        for button, name in (
            (self.start_button, "Go to review start"),
            (self.previous_button, "Previous review position"),
            (self.next_button, "Next review position"),
            (self.end_button, "Go to review end"),
        ):
            button.setAccessibleName(name)
        for column, button in enumerate(
            (self.start_button, self.previous_button, self.next_button, self.end_button)
        ):
            controls.addWidget(button, 0, column)
        layout.addLayout(controls)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setAccessibleName("Review position")
        self.slider.setAccessibleDescription(
            "Select a position from the start to the end of the game"
        )
        self.slider.setMinimum(0)
        layout.addWidget(self.slider)
        self.position_label = QLabel("Start")
        self.played_label = QLabel("Played: —")
        self.best_label = QLabel("Engine best: —")
        self.evaluation_label = QLabel("Evaluation: —")
        for label in (
            self.position_label,
            self.played_label,
            self.best_label,
            self.evaluation_label,
        ):
            label.setWordWrap(True)
            layout.addWidget(label)
        actions = QGridLayout()
        self.show_line_button = QPushButton("Show Best Line")
        self.retry_move_button = QPushButton("Retry Move")
        self.hint_button = QPushButton("Hint")
        self.show_line_button.setAccessibleName("Show engine best line")
        self.retry_move_button.setAccessibleName("Retry current move")
        self.hint_button.setAccessibleName("Show retry hint")
        self.hint_button.hide()
        actions.addWidget(self.show_line_button, 0, 0)
        actions.addWidget(self.retry_move_button, 0, 1)
        actions.addWidget(self.hint_button, 0, 2)
        layout.addLayout(actions)
        self.show_line_button.clicked.connect(self.show_line_requested.emit)
        self.retry_move_button.clicked.connect(self.retry_requested.emit)
        self.hint_button.clicked.connect(self.hint_requested.emit)
        self.start_button.clicked.connect(lambda: self.index_changed.emit(0))
        self.previous_button.clicked.connect(
            lambda: self.index_changed.emit(max(0, self.slider.value() - 1))
        )
        self.next_button.clicked.connect(
            lambda: self.index_changed.emit(min(self.slider.maximum(), self.slider.value() + 1))
        )
        self.end_button.clicked.connect(lambda: self.index_changed.emit(self.slider.maximum()))
        self.slider.valueChanged.connect(self.index_changed.emit)
        self.shortcuts: list[QShortcut] = []
        for key, button in (
            (Qt.Key.Key_Left, self.previous_button),
            (Qt.Key.Key_Right, self.next_button),
            (Qt.Key.Key_Home, self.start_button),
            (Qt.Key.Key_End, self.end_button),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(button.click)
            self.shortcuts.append(shortcut)

    def configure(self, total: int) -> None:
        self.slider.setRange(0, total)
        self.set_index(total)

    def set_index(self, index: int) -> None:
        with QSignalBlocker(self.slider):
            self.slider.setValue(index)
        total = self.slider.maximum()
        self.position_label.setText(f"Position: {index} / {total}")
        self.start_button.setEnabled(index > 0)
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < total)
        self.end_button.setEnabled(index < total)
        self.graph.set_selected(index)
        self.next_key_button.setEnabled(any(ply > index for ply in self.key_moments))

    def set_analysis(self, analysis: GameAnalysis | None, player_color: str) -> None:
        if analysis is None:
            self.key_moments = ()
            self.graph.set_moves((), ())
        else:
            self.key_moments = tuple(
                ply
                for ply in analysis.turning_points
                if analysis.moves[ply - 1].mover == player_color
            )
            self.graph.set_moves(analysis.moves, self.key_moments)
        self.set_index(self.slider.value())

    def set_retry_mode(self, active: bool) -> None:
        self.hint_button.setVisible(active)
        self.show_line_button.setEnabled(not active)
        self.retry_move_button.setText("Return to Review" if active else "Retry Move")
        self.slider.setEnabled(not active)
        self.next_key_button.setEnabled(
            not active and any(p > self.slider.value() for p in self.key_moments)
        )

    def _next_key(self) -> None:
        current = self.slider.value()
        next_ply = next((ply for ply in self.key_moments if ply > current), None)
        if next_ply is not None:
            self.index_changed.emit(next_ply)

    def set_details(self, played: str, best: str, evaluation: str) -> None:
        self.played_label.setText(f"Played: {played}")
        self.best_label.setText(f"Engine best: {best}")
        self.evaluation_label.setText(f"Evaluation before move: {evaluation}")
