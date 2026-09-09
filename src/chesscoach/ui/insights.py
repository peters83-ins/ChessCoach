"""Local, inspectable learning insights panel."""

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chesscoach.chess.openings import OpeningMatch
from chesscoach.coach.insights import opening_stats, recommend_next_action
from chesscoach.courses.catalog import CourseCatalog
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameDatabase


class InsightsDialog(QDialog):
    def __init__(
        self,
        repository: CoachRepository,
        database: GameDatabase,
        catalog: CourseCatalog | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.repository, self.database = repository, database
        self.catalog = catalog or CourseCatalog()
        self.setWindowTitle("Learning Insights")
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.mastery = QProgressBar()
        self.mastery.setRange(0, 100)
        self.mastery.setFormat("Course mastery: %p%")
        layout.addWidget(self.mastery)
        layout.addWidget(QLabel("Opening results (shown after five qualifying games)"))
        self.openings = QTableWidget(0, 4)
        self.openings.setHorizontalHeaderLabels(("Opening", "Games", "Wins", "Losses"))
        self.openings.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.openings, 1)
        self.refresh()

    def refresh(self) -> None:
        games = self.database.list_games()
        records = tuple(
            (OpeningMatch("", game.opening), game.result, game.player_color)
            for game in games
            if game.opening != "Unknown opening"
        )
        stats = opening_stats(records)
        self.openings.setRowCount(len(stats))
        for row, stat in enumerate(stats):
            for column, value in enumerate(
                (stat.opening, str(stat.games), str(stat.wins), str(stat.losses))
            ):
                self.openings.setItem(row, column, QTableWidgetItem(value))
        due = len(self.repository.due_course_mastery()) + self.repository.practice_progress().due
        weaknesses = self.repository.weakness_details()
        theme = weaknesses[0].theme if weaknesses else ""
        self.mastery.setValue(self._mastery_percent())
        self.summary.setText(
            f"{len(games)} saved game(s). {recommend_next_action(due, theme, len(games))} "
            "All metrics are local Chess Coach estimates."
        )

    def _mastery_percent(self) -> int:
        mastery = [
            item
            for course in self.catalog.courses
            for item in self.repository.course_mastery(course.id)
        ]
        if not mastery:
            return 0
        return round(100 * sum(min(1, item.level) for item in mastery) / len(mastery))
