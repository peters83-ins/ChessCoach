"""Move navigation and engine comparison details for a loaded game."""

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget


class GameReview(QWidget):
    index_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        controls = QGridLayout()
        self.start_button = QPushButton("|◀")
        self.previous_button = QPushButton("◀")
        self.next_button = QPushButton("▶")
        self.end_button = QPushButton("▶|")
        for column, button in enumerate(
            (self.start_button, self.previous_button, self.next_button, self.end_button)
        ):
            controls.addWidget(button, 0, column)
        layout.addLayout(controls)
        self.slider = QSlider(Qt.Orientation.Horizontal)
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
        self.start_button.clicked.connect(lambda: self.index_changed.emit(0))
        self.previous_button.clicked.connect(
            lambda: self.index_changed.emit(max(0, self.slider.value() - 1))
        )
        self.next_button.clicked.connect(
            lambda: self.index_changed.emit(min(self.slider.maximum(), self.slider.value() + 1))
        )
        self.end_button.clicked.connect(lambda: self.index_changed.emit(self.slider.maximum()))
        self.slider.valueChanged.connect(self.index_changed.emit)

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

    def set_details(self, played: str, best: str, evaluation: str) -> None:
        self.played_label.setText(f"Played: {played}")
        self.best_label.setText(f"Engine best: {best}")
        self.evaluation_label.setText(f"Evaluation before move: {evaluation}")
