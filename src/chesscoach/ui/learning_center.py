"""Persistent weakness and spaced-practice navigation."""

from datetime import UTC, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chesscoach.storage.coach import CoachRepository


class WeaknessDashboardDialog(QDialog):
    example_requested = Signal(str, int)

    def __init__(self, repository: CoachRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("Weakness Dashboard")
        self.resize(780, 440)
        layout = QVBoxLayout(self)
        note = QLabel(
            "Themes come from engine-verified positions. Each game contributes at most "
            "one severity value per theme, so one game cannot dominate the profile."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ("Theme", "Score", "Games", "Confidence", "Trend", "Why", "Recent example")
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAccessibleName("Engine-grounded weakness themes")
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.open_button = QPushButton("Open Example")
        self.dismiss_button = QPushButton("Dismiss Theme…")
        actions.addWidget(self.open_button)
        actions.addWidget(self.dismiss_button)
        layout.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.open_button.clicked.connect(self._open)
        self.dismiss_button.clicked.connect(self._dismiss)
        self.refresh()

    def refresh(self) -> None:
        details = self.repository.weakness_details()
        self.table.setRowCount(len(details))
        for row, detail in enumerate(details):
            example = detail.examples[0] if detail.examples else ("", 0)
            values = (
                detail.theme.replace("_", " ").title(),
                f"{detail.score:.2f}",
                str(detail.occurrences),
                f"{detail.confidence:.0%}",
                detail.trend.title(),
                detail.reason,
                f"Game {example[0][:8]} · ply {example[1]}" if example[0] else "—",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, detail.theme)
                item.setData(Qt.ItemDataRole.UserRole + 1, example)
                self.table.setItem(row, column, item)
        if details:
            self.table.selectRow(0)
        self.open_button.setEnabled(bool(details and details[0].examples))
        self.dismiss_button.setEnabled(bool(details))

    def _open(self) -> None:
        item = self.table.item(self.table.currentRow(), 0)
        example = item.data(Qt.ItemDataRole.UserRole + 1) if item else None
        if example and example[0]:
            self.example_requested.emit(str(example[0]), int(example[1]))
            self.accept()

    def _dismiss(self) -> None:
        item = self.table.item(self.table.currentRow(), 0)
        if item is None:
            return
        answer = QMessageBox.question(
            self,
            "Dismiss weakness?",
            "Hide this inferred theme from your profile? Supporting game data is retained.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.repository.dismiss_weakness(str(item.data(Qt.ItemDataRole.UserRole)))
            self.refresh()


class PracticeQueueDialog(QDialog):
    def __init__(self, repository: CoachRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.setWindowTitle("Practice Queue")
        self.resize(700, 440)
        layout = QVBoxLayout(self)
        self.progress = QLabel()
        self.progress.setWordWrap(True)
        layout.addWidget(self.progress)
        note = QLabel(
            "Personal positions also reinforce the lesson concept. Correct follow-up moves "
            "measure progress on that same theme."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("Theme", "Source", "Due", "Interval"))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAccessibleName("Scheduled personal practice positions")
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        self.start_button = QPushButton("Practice Selected")
        close = QPushButton("Close")
        actions.addWidget(self.start_button)
        actions.addWidget(close)
        layout.addLayout(actions)
        self.start_button.clicked.connect(self._start)
        close.clicked.connect(self.accept)
        self.refresh()

    def refresh(self) -> None:
        progress = self.repository.practice_progress()
        self.progress.setText(
            f"Due today: {progress.due} · Total: {progress.total} · "
            f"Completed attempts: {progress.successful}/{progress.attempted}"
        )
        now = datetime.now(UTC).isoformat()
        items = tuple(item for item in self.repository.practice_items() if item.due_at <= now)
        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            values = (
                item.theme.replace("_", " ").title(),
                f"Game {item.source_game_id[:8]} · ply {item.source_ply}",
                item.due_at[:10],
                f"{item.interval_days} day(s)",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.id)
                self.table.setItem(row, column, cell)
        if items:
            self.table.selectRow(0)
        self.start_button.setEnabled(bool(items))

    def _start(self) -> None:
        selected = self.table.item(self.table.currentRow(), 0)
        if selected is None:
            return
        item_id = str(selected.data(Qt.ItemDataRole.UserRole))
        item = next(
            (value for value in self.repository.practice_items() if value.id == item_id), None
        )
        if item is None:
            return
        from chesscoach.ui.coach_panel import PracticeDialog

        PracticeDialog(item, self.repository, self).exec()
        self.refresh()
