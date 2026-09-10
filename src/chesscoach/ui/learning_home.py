"""A concise, action-oriented learning home."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from chesscoach.courses.catalog import CourseCatalog
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameDatabase


class LearningHomeDialog(QDialog):
    """Show the learner's next useful local activity in one screen."""

    action_requested = Signal(str)

    def __init__(
        self,
        repository: CoachRepository,
        catalog: CourseCatalog,
        database: GameDatabase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository, self.catalog, self.database = repository, catalog, database
        self.setWindowTitle("Learn")
        self.resize(560, 430)
        layout = QVBoxLayout(self)
        title = QLabel("<h2>What should you learn next?</h2>")
        layout.addWidget(title)
        self.recommendation = QLabel()
        self.recommendation.setWordWrap(True)
        layout.addWidget(self.recommendation)
        self.next_action = QPushButton("Start recommended activity")
        self.next_action.setObjectName("primaryAction")
        self.next_action.setAccessibleName("Start recommended learning activity")
        self.next_action.clicked.connect(self._choose_recommended)
        layout.addWidget(self.next_action)
        self.continue_course = QPushButton("Continue course")
        self.practice_due = QPushButton("Practice due today")
        self.review_latest = QPushButton("Review latest game")
        self.weakest = QPushButton("Study weakest theme")
        self.course_library = QPushButton("Browse courses")
        for button, action in (
            (self.continue_course, "continue"),
            (self.practice_due, "practice"),
            (self.review_latest, "latest"),
            (self.weakest, "weaknesses"),
            (self.course_library, "courses"),
        ):
            button.clicked.connect(lambda checked=False, value=action: self._choose(value))
            layout.addWidget(button)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        self.refresh()

    def refresh(self) -> None:
        practice = self.repository.practice_progress()
        due_courses = self.repository.due_course_mastery()
        progress = self.repository.course_progress()
        games = self.database.list_games()
        weaknesses = self.repository.weakness_details()
        course_available = bool(self.catalog.courses)
        self.next_action_key = "courses"
        self.continue_course.setEnabled(course_available)
        self.course_library.setEnabled(course_available)
        self.practice_due.setEnabled(practice.due > 0 or bool(due_courses))
        self.review_latest.setEnabled(bool(games))
        self.weakest.setEnabled(bool(weaknesses))
        self.continue_course.setToolTip(
            "Resume the next due decision or saved course module."
            if course_available
            else "No offline courses are installed."
        )
        self.practice_due.setToolTip(
            "Practice due decisions from games and courses."
            if self.practice_due.isEnabled()
            else "No practice is due yet."
        )
        self.review_latest.setToolTip(
            "Review the latest saved game." if games else "Save or import a game first."
        )
        self.weakest.setToolTip(
            "Practice your most frequent theme."
            if weaknesses
            else "Analyze a game to identify a learning theme."
        )
        if practice.due or due_courses:
            self.next_action_key = "practice"
            self.next_action.setText("Practice due decisions")
            self.recommendation.setText(
                "Practice is due. A short local session will reinforce your current decisions."
            )
        elif progress:
            self.next_action_key = "continue"
            self.next_action.setText("Continue course")
            self.recommendation.setText(
                "Continue your enrolled course and keep building decision-level mastery."
            )
        elif games:
            self.next_action_key = "latest"
            self.next_action.setText("Review latest game")
            self.recommendation.setText(
                "Review your latest saved game to find the next practice position."
            )
        elif weaknesses:
            self.next_action_key = "weaknesses"
            self.next_action.setText("Study weakest theme")
            self.recommendation.setText(
                f"Your current focus is {weaknesses[0].theme.replace('_', ' ')}."
            )
        elif course_available:
            self.next_action_key = "continue"
            self.next_action.setText("Start an opening course")
            self.recommendation.setText(
                "Start a short opening course to build a practical repertoire."
            )
        else:
            self.next_action.setText("Browse learning options")
            self.recommendation.setText(
                "Play or import a game, then return here for a grounded next step."
            )

        self.next_action.setToolTip(self.recommendation.text())

    def _choose_recommended(self) -> None:
        self._choose(self.next_action_key)

    def _choose(self, action: str) -> None:
        if action == "continue":
            due = self.repository.due_course_mastery()
            if due:
                self.action_requested.emit(f"course:{due[0].course_id}:{due[0].exercise_id}")
                self.accept()
                return
            progress = self.repository.course_progress()
            if progress:
                self.action_requested.emit(f"course:{progress[0].course_id}")
            elif self.catalog.courses:
                self.action_requested.emit(f"course:{self.catalog.courses[0].id}")
            else:
                self.action_requested.emit("courses")
            self.accept()
            return
        self.action_requested.emit(action)
        self.accept()
