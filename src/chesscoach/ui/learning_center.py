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

from chesscoach.coach.adaptive import LearningItem, compose_daily_session
from chesscoach.coach.models import PracticeItem
from chesscoach.courses.catalog import CourseCatalog
from chesscoach.courses.models import Course, CourseExercise
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
    def __init__(
        self,
        repository: CoachRepository,
        parent: QWidget | None = None,
        catalog: CourseCatalog | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.catalog = catalog or CourseCatalog()
        self._personal: tuple[PracticeItem, ...] = ()
        self._daily: tuple[LearningItem, ...] = ()
        self._personal_by_id: dict[str, PracticeItem] = {}
        self._course_by_id: dict[str, tuple[Course, CourseExercise]] = {}
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
        self.table.setHorizontalHeaderLabels(("Source", "Theme", "Due", "Action"))
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
        now = datetime.now(UTC).isoformat()
        self._personal = tuple(
            item for item in self.repository.practice_items() if item.due_at <= now
        )
        self._personal_by_id = {item.id: item for item in self._personal}
        course_mastery = self.repository.due_course_mastery()
        self._course_by_id = {}
        course_items: list[LearningItem] = []
        for mastery in course_mastery:
            course = next(
                (value for value in self.catalog.courses if value.id == mastery.course_id), None
            )
            if course is None:
                continue
            exercise = next(
                (value for value in course.exercises if value.id == mastery.exercise_id), None
            )
            if exercise is None:
                continue
            identifier = f"{course.id}:{exercise.id}:{mastery.decision_index}"
            self._course_by_id[identifier] = (course, exercise)
            course_items.append(
                LearningItem("course", identifier, exercise.tags[0] if exercise.tags else "course")
            )
        concepts = tuple(
            LearningItem("concept", f"theme:{detail.theme}", detail.theme)
            for detail in self.repository.weakness_details()
        )
        personal_items = tuple(
            LearningItem("personal", item.id, item.theme) for item in self._personal
        )
        self._daily = compose_daily_session(personal_items, tuple(course_items), concepts)
        counts = {
            source: sum(item.source == source for item in self._daily)
            for source in ("personal", "course", "concept")
        }
        self.progress.setText(
            f"Due today: {progress.due} · Daily session: {len(self._daily)}/10 · "
            f"Personal {counts['personal']} · Courses {counts['course']} · "
            f"Concepts {counts['concept']}"
        )
        self.table.setRowCount(len(self._daily))
        for row, item in enumerate(self._daily):
            if item.source == "personal":
                practice = self._personal_by_id[item.identifier]
                theme, due, action = (
                    practice.theme.replace("_", " ").title(),
                    practice.due_at[:10],
                    "Practice",
                )
            elif item.source == "course":
                theme, due, action = item.theme.replace("_", " ").title(), "today", "Course"
            else:
                theme, due, action = item.theme.replace("_", " ").title(), "today", "Reinforce"
            values = (
                item.source.title(),
                theme,
                due,
                action,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, (item.source, item.identifier))
                self.table.setItem(row, column, cell)
        if self._daily:
            self.table.selectRow(0)
        self.start_button.setEnabled(bool(self._daily))

    def _start(self) -> None:
        selected = self.table.item(self.table.currentRow(), 0)
        if selected is None:
            return
        source, identifier = selected.data(Qt.ItemDataRole.UserRole)
        if source == "personal":
            from chesscoach.ui.coach_panel import PracticeDialog

            item = self._personal_by_id.get(identifier)
            if item is not None:
                PracticeDialog(item, self.repository, self).exec()
        elif source == "course":
            from chesscoach.ui.course_center import CoursePlayerDialog

            course, exercise = self._course_by_id[identifier]
            index = course.exercises.index(exercise)
            CoursePlayerDialog(course, self.repository, self, start_index=index).exec()
        else:
            QMessageBox.information(
                self,
                "Theme reinforcement",
                "Choose a personal or course position to practice this theme.",
            )
        self.refresh()
