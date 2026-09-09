"""Course library and short offline course player."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from chesscoach.chess.game import Game
from chesscoach.coach.models import PracticeItem
from chesscoach.coach.training import TrainingSession
from chesscoach.courses.catalog import CourseCatalog
from chesscoach.courses.models import Course
from chesscoach.storage.coach import CoachRepository
from chesscoach.ui.chess_board import ChessBoard


class CourseLibraryDialog(QDialog):
    """Browse locally installed courses and launch a detail/player window."""

    def __init__(
        self, catalog: CourseCatalog, repository: CoachRepository, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.repository = repository
        self.setWindowTitle("Course library")
        self.resize(620, 420)
        layout = QVBoxLayout(self)
        filters = QHBoxLayout()
        self.search = QLabel("Search")
        filters.addWidget(self.search)
        from PySide6.QtWidgets import QLineEdit

        self.query = QLineEdit()
        self.query.setPlaceholderText("Opening, theme, or course title")
        filters.addWidget(self.query, 1)
        self.side = QComboBox()
        self.side.addItems(["All sides", "White", "Black", "Both"])
        filters.addWidget(self.side)
        self.level = QSpinBox()
        self.level.setRange(0, 3000)
        self.level.setSpecialValueText("Any level")
        self.level.setValue(0)
        self.level.setPrefix("Rating ")
        filters.addWidget(self.level)
        layout.addLayout(filters)
        self.list = QListWidget()
        self.list.setAccessibleName("Course list")
        layout.addWidget(self.list, 1)
        self.empty = QLabel("No courses installed yet. Starter courses will appear here.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        self.start = QPushButton("Start / Continue")
        self.start.setEnabled(False)
        layout.addWidget(self.start)
        self.query.textChanged.connect(self.refresh)
        self.side.currentTextChanged.connect(self.refresh)
        self.level.valueChanged.connect(self.refresh)
        self.list.currentItemChanged.connect(
            lambda *_: self.start.setEnabled(self.list.currentItem() is not None)
        )
        self.start.clicked.connect(self.open_selected)
        self.refresh()

    def refresh(self) -> None:
        side = self.side.currentText().split()[0].lower()
        if side == "all":
            side = "all"
        level = self.level.value() or None
        courses = self.catalog.search(self.query.text(), side, level)
        self.list.clear()
        for course in courses:
            item = QListWidgetItem(
                f"{course.title}  ·  {course.level_min}–{course.level_max}  · "
                f"{course.estimated_minutes} min"
            )
            item.setData(Qt.ItemDataRole.UserRole, course.id)
            self.list.addItem(item)
        self.empty.setVisible(not courses)
        self.start.setEnabled(bool(courses))

    def open_selected(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        course = next(
            course
            for course in self.catalog.courses
            if course.id == item.data(Qt.ItemDataRole.UserRole)
        )
        CourseDetailDialog(course, self.repository, self).exec()

    def open_course(self, course_id: str) -> None:
        course = next((value for value in self.catalog.courses if value.id == course_id), None)
        if course is not None:
            CourseDetailDialog(course, self.repository, self).exec()


class CourseDetailDialog(QDialog):
    def __init__(
        self, course: Course, repository: CoachRepository, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.course, self.repository = course, repository
        self.setWindowTitle(course.title)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"<b>{course.title}</b><br>{course.description}<br>"
                f"Estimated time: {course.estimated_minutes} minutes<br>"
                f"{course.attribution}"
            )
        )
        self.modules = QListWidget()
        for module in course.modules:
            self.modules.addItem(
                f"{module.order + 1}. {module.title} ({len(module.exercise_ids)} exercises)"
            )
        layout.addWidget(self.modules)
        self.progress = QLabel()
        layout.addWidget(self.progress)
        self.start = QPushButton("Start")
        layout.addWidget(self.start)
        self.start.clicked.connect(self.start_course)
        self.update_progress()

    def update_progress(self) -> None:
        progress = self.repository.course_progress(self.course.id)
        self.progress.setText(
            "Enrolled — continue where you left off." if progress else "Not started"
        )
        self.start.setText("Continue" if progress else "Start")

    def start_course(self) -> None:
        self.repository.enroll_course(self.course)
        progress = self.repository.course_progress(self.course.id)
        module_id = progress[0].last_module_id if progress else ""
        start_index = next(
            (
                index
                for index, exercise in enumerate(self.course.exercises)
                if exercise.module_id == module_id
            ),
            0,
        )
        CoursePlayerDialog(self.course, self.repository, self, start_index=start_index).exec()
        self.update_progress()


class CoursePlayerDialog(QDialog):
    def __init__(
        self,
        course: Course,
        repository: CoachRepository,
        parent: QWidget | None = None,
        *,
        start_index: int = 0,
    ) -> None:
        super().__init__(parent)
        self.course, self.repository = course, repository
        self.exercise_index = max(0, min(start_index, len(course.exercises) - 1))
        self.hints_used = 0
        self.setWindowTitle(f"Learn: {course.title}")
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        self.concept = QLabel()
        self.concept.setWordWrap(True)
        layout.addWidget(self.concept)
        self.board = ChessBoard(self._game_for_current())
        self.session = self._session_for_current()
        self.board.game = self.session.game
        self.board.game_changed.connect(self.on_move)
        layout.addWidget(self.board, 1)
        self.status = QLabel()
        layout.addWidget(self.status)
        controls = QHBoxLayout()
        self.hint = QPushButton("Hint")
        self.next_button = QPushButton("Next exercise")
        self.next_button.setEnabled(False)
        controls.addWidget(self.hint)
        controls.addWidget(self.next_button)
        layout.addLayout(controls)
        self.hint.clicked.connect(self.show_hint)
        self.next_button.clicked.connect(self.next_exercise)
        self._render()

    def _game_for_current(self) -> Game:
        return chess_game_from_fen(self.course.exercises[self.exercise_index].fen)

    def _session_for_current(self) -> TrainingSession:
        exercise = self.course.exercises[self.exercise_index]
        item = PracticeItem(
            id=f"course:{self.course.id}:{exercise.id}",
            profile_id="default",
            source_game_id="",
            source_ply=0,
            fen=exercise.fen,
            theme=exercise.tags[0] if exercise.tags else "course",
            solution=exercise.line,
            alternatives=(),
            alternative_lines=exercise.alternatives,
        )
        return TrainingSession(item)

    def _render(self) -> None:
        exercise = self.course.exercises[self.exercise_index]
        self.concept.setText(
            f"<b>{self.exercise_index + 1}/{len(self.course.exercises)} — {exercise.prompt}</b><br>"
            f"{exercise.explanation}"
        )
        self.status.setText("Your move. Select a piece, then a destination.")
        self.next_button.setEnabled(False)
        self.board.input_allowed = True
        self.board.refresh()

    def on_move(self) -> None:
        if self.session.completed:
            self.status.setText("Completed. Review the idea, then continue.")
            self.next_button.setEnabled(True)
            self.board.input_allowed = False
            self.repository.record_course_attempt(
                self.course.id,
                self.course.exercises[self.exercise_index].id,
                self.session.decision_index,
                "",
                True,
                self.hints_used,
            )
            return
        move_stack = self.session.game.position.move_stack
        if not move_stack:
            return
        move = move_stack[-1]
        result = self.session.attempt(move)
        if result.mistake:
            self.status.setText("Mistake — try this decision again.")
            self.hints_used = min(3, self.hints_used + 1)
            QTimer.singleShot(700, self._rollback)
            self.repository.record_course_attempt(
                self.course.id,
                self.course.exercises[self.exercise_index].id,
                result.decision_index,
                move.uci(),
                False,
                self.hints_used,
            )
        elif result.completed:
            self.on_move()
        else:
            self.status.setText("Correct. Follow the reply, then find the next move.")

    def _rollback(self) -> None:
        self.board.game = self.session.game
        self.board.refresh()

    def show_hint(self) -> None:
        exercise = self.course.exercises[self.exercise_index]
        self.hints_used = min(len(exercise.hints), self.hints_used + 1)
        self.status.setText(
            exercise.hints[self.hints_used - 1] if self.hints_used else "Look for the course idea."
        )

    def next_exercise(self) -> None:
        self.exercise_index += 1
        if self.exercise_index >= len(self.course.exercises):
            self.accept()
            return
        self.hints_used = 0
        self.session = self._session_for_current()
        self.board.game = self.session.game
        self._render()


def chess_game_from_fen(fen: str) -> Game:
    return Game(fen)
