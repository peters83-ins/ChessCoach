"""Local, inspectable learning insights panel."""

from datetime import UTC, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chesscoach.chess.openings import OpeningMatch
from chesscoach.coach.insights import (
    analyzed_theme_counts,
    opening_departure_transfer,
    opening_stats,
    period_comparison,
    phase_accuracy,
    phase_transfer,
    recommend_next_action,
    theme_frequency,
    transfer_metric,
)
from chesscoach.courses.catalog import CourseCatalog
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameDatabase


class InsightsDialog(QDialog):
    example_requested = Signal(str, int)
    theme_practice_requested = Signal(str)
    theme_course_requested = Signal(str)

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
        layout.addWidget(QLabel("Recurring themes from analyzed positions"))
        self.themes = QTableWidget(0, 2)
        self.themes.setHorizontalHeaderLabels(("Theme", "Occurrences"))
        self.themes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.themes.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.themes.itemSelectionChanged.connect(self._update_example_button)
        layout.addWidget(self.themes)
        self.open_example = QPushButton("Open supporting position")
        self.open_example.setEnabled(False)
        self.open_example.clicked.connect(self._open_example)
        layout.addWidget(self.open_example)
        self.practice_theme = QPushButton("Practice selected theme")
        self.practice_theme.setEnabled(False)
        self.practice_theme.clicked.connect(self._practice_theme)
        layout.addWidget(self.practice_theme)
        self.course_theme = QPushButton("Open related course")
        self.course_theme.setEnabled(False)
        self.course_theme.clicked.connect(self._open_course)
        layout.addWidget(self.course_theme)
        layout.addWidget(QLabel("Accuracy by game phase (analyzed player moves)"))
        self.phases = QTableWidget(0, 3)
        self.phases.setHorizontalHeaderLabels(("Phase", "Accuracy", "Moves"))
        self.phases.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.phases)
        self.phase_transfer_label = QLabel()
        self.phase_transfer_label.setWordWrap(True)
        layout.addWidget(self.phase_transfer_label)
        self.opening_transfer_label = QLabel()
        self.opening_transfer_label.setWordWrap(True)
        layout.addWidget(self.opening_transfer_label)
        self.transfer = QLabel()
        self.transfer.setWordWrap(True)
        layout.addWidget(self.transfer)
        self.periods = QLabel()
        self.periods.setWordWrap(True)
        layout.addWidget(self.periods)
        self._theme_examples: dict[str, tuple[tuple[str, int], ...]] = {}
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
        details = self.repository.weakness_details()
        self._theme_examples = {detail.theme: detail.examples for detail in details}
        analyzed = self.repository.stored_move_analyses()
        frequencies = analyzed_theme_counts(analyzed)
        if not frequencies:
            frequencies = theme_frequency(
                detail.theme
                for detail in details
                for _ in range(detail.occurrences)
            )
        self.themes.setRowCount(len(frequencies))
        for row, (theme_name, count) in enumerate(frequencies):
            item = QTableWidgetItem(theme_name.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, theme_name)
            self.themes.setItem(row, 0, item)
            self.themes.setItem(row, 1, QTableWidgetItem(str(count)))
        phases = phase_accuracy(analyzed, "white")
        self.phases.setRowCount(len(phases))
        for row, (phase, accuracy, count) in enumerate(phases):
            for column, value in enumerate((phase.title(), f"{accuracy:.1f}%", str(count))):
                self.phases.setItem(row, column, QTableWidgetItem(value))
        game_dates = {game.id: game.saved_at for game in games}
        phase_records = []
        for game_id, move in self.repository.stored_move_analyses_by_game():
            saved_at = game_dates.get(game_id)
            if saved_at is None or move.mover != "white":
                continue
            try:
                observed = datetime.fromisoformat(saved_at)
            except ValueError:
                continue
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            phase_records.append((move.phase.value, move.accuracy, observed))
        phase_changes = phase_transfer(phase_records)
        self.phase_transfer_label.setText(
            "Phase transfer: "
            + "; ".join(
                f"{phase.title()} {recent:.1f}% vs {prior:.1f}% earlier"
                for phase, recent, prior, _ in phase_changes
            )
            if phase_changes
            else (
                "Phase transfer comparisons require three recent and three earlier "
                "analyzed moves per phase."
            )
        )
        opening_records = []
        for game in games:
            data = self.database.load_game(game.id)
            if data is None:
                continue
            try:
                observed = datetime.fromisoformat(game.saved_at)
            except ValueError:
                continue
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            opening_records.append((data.moves, observed))
        opening_transfer = opening_departure_transfer(opening_records)
        self.opening_transfer_label.setText(
            (
                f"Opening transfer: {opening_transfer[0]:.0%} of recent game plies "
                f"followed a reviewed line vs {opening_transfer[1]:.0%} earlier "
                f"({opening_transfer[2]} games)."
            )
            if opening_transfer
            else (
                "Opening transfer comparisons require three recent and three earlier "
                "recognized games."
            )
        )
        due = len(self.repository.due_course_mastery()) + self.repository.practice_progress().due
        theme = details[0].theme if details else ""
        self.mastery.setValue(self._mastery_percent())
        transfer_rows = []
        for theme_name, (before, after) in self.repository.practice_transfer_observations().items():
            metric = transfer_metric(theme_name, before, after)
            if metric is not None:
                transfer_rows.append(
                    f"{theme_name.replace('_', ' ').title()}: "
                    f"{metric.after_rate:.0%} after vs {metric.before_rate:.0%} before "
                    f"({metric.delta:+.0%}, {metric.sample_size} attempts)"
                )
        self.transfer.setText(
            "Transfer: " + "; ".join(transfer_rows)
            if transfer_rows
            else "Transfer comparisons will appear after five qualifying before-and-after "
            "practice observations for a theme."
        )
        self.periods.setText(self._period_summary(games))
        self.summary.setText(
            f"{len(games)} saved game(s). {recommend_next_action(due, theme, len(games))} "
            "All metrics are local Chess Coach estimates."
        )

    def _period_summary(self, games: tuple[object, ...]) -> str:
        values: list[tuple[float, datetime]] = []
        for game in games:
            saved_at = getattr(game, "saved_at", "")
            try:
                observed = datetime.fromisoformat(saved_at)
            except ValueError:
                continue
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=UTC)
            result = getattr(game, "result", "")
            color = getattr(game, "player_color", "white")
            won = (result == "1-0" and color == "white") or (
                result == "0-1" and color == "black"
            )
            score = 1.0 if won else 0.5 if result == "1/2-1/2" else 0.0
            values.append((score, observed))
        comparison = period_comparison(values)
        if comparison is None:
            return "Recent vs previous performance will appear after three games in each period."
        recent, prior = comparison
        delta = recent - prior
        direction = "up" if delta >= 0 else "down"
        return (
            f"Recent performance: {recent:.0%} ({direction} {abs(delta):.0%} "
            "vs previous period)."
        )

    def _update_example_button(self) -> None:
        theme = self._selected_theme()
        self.open_example.setEnabled(bool(theme and self._theme_examples.get(theme, ())))
        self.practice_theme.setEnabled(theme is not None)
        self.course_theme.setEnabled(bool(theme and self._has_course_theme(theme)))

    def _open_example(self) -> None:
        theme = self._selected_theme()
        examples = self._theme_examples.get(theme, ()) if theme else ()
        if examples:
            game_id, ply = examples[0]
            self.example_requested.emit(game_id, ply)

    def _practice_theme(self) -> None:
        theme = self._selected_theme()
        if theme is not None:
            self.theme_practice_requested.emit(theme)

    def _open_course(self) -> None:
        theme = self._selected_theme()
        if theme is not None and self._has_course_theme(theme):
            self.theme_course_requested.emit(theme)

    def _has_course_theme(self, theme: str) -> bool:
        return any(
            theme in exercise.tags
            for course in self.catalog.courses
            for exercise in course.exercises
        )

    def _selected_theme(self) -> str | None:
        rows = self.themes.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.themes.item(rows[0].row(), 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def _mastery_percent(self) -> int:
        mastery = [
            item
            for course in self.catalog.courses
            for item in self.repository.course_mastery(course.id)
        ]
        if not mastery:
            return 0
        return round(100 * sum(min(1, item.level) for item in mastery) / len(mastery))
