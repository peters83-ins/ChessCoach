"""Full-game coaching summary, filters, practice, and lesson entry points."""

from collections import Counter

import chess
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chesscoach.chess.game import Game
from chesscoach.chess.openings import recognize_opening
from chesscoach.chess.pgn import san_variation
from chesscoach.coach.models import CoachBundle, Lesson, MoveClassification, PracticeItem
from chesscoach.coach.scoring import player_accuracy
from chesscoach.coach.training import TrainingSession
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.chess_board import ChessBoard


class CoachPanel(QWidget):
    analyze_requested = Signal()
    cancel_requested = Signal()
    practice_requested = Signal()
    lessons_requested = Signal()
    weaknesses_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bundle: CoachBundle | None = None
        self.player_color = "white"
        self.current_ply = 0
        self.verbosity = "detailed"
        self.opening_summary = "Opening: not identified"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        self.analyze_button = QPushButton("Analyze Full Game")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.hide()
        controls.addWidget(self.analyze_button)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        self.ai_status = QLabel("Local coach available")
        self.ai_status.setWordWrap(True)
        layout.addWidget(self.ai_status)
        self.cloud_toggle = QCheckBox("Use OpenAI for critical-move explanations")
        self.cloud_toggle.setEnabled(False)
        self.cloud_toggle.setToolTip(
            "Sends selected positions and engine facts, not the full game or API key."
        )
        layout.addWidget(self.cloud_toggle)
        self.filter = QComboBox()
        self.filter.addItem("My moves", "player")
        self.filter.addItem("Mistakes and blunders", "critical")
        self.filter.addItem("Both sides", "both")
        self.filter.addItem("All moves", "all")
        layout.addWidget(self.filter)
        self.report = QLabel("Run full-game analysis for coaching and accuracy.")
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        self.report.setWordWrap(True)
        layout.addWidget(self.report)
        layout.addWidget(self.feedback)
        learning = QHBoxLayout()
        self.practice_button = QPushButton("Practice")
        self.lessons_button = QPushButton("Lessons")
        self.weaknesses_button = QPushButton("Weaknesses")
        self.practice_button.setEnabled(False)
        self.lessons_button.setEnabled(False)
        learning.addWidget(self.practice_button)
        learning.addWidget(self.lessons_button)
        learning.addWidget(self.weaknesses_button)
        layout.addLayout(learning)
        self.analyze_button.clicked.connect(self.analyze_requested.emit)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.practice_button.clicked.connect(self.practice_requested.emit)
        self.lessons_button.clicked.connect(self.lessons_requested.emit)
        self.weaknesses_button.clicked.connect(self.weaknesses_requested.emit)
        self.filter.currentIndexChanged.connect(lambda: self.show_ply(self.current_ply))

    def set_preferences(self, perspective: str, verbosity: str) -> None:
        index = self.filter.findData(perspective)
        self.filter.setCurrentIndex(index if index >= 0 else 0)
        self.verbosity = verbosity if verbosity in ("concise", "detailed") else "detailed"
        self.show_ply(self.current_ply)

    def set_ai_ready(self, ready: bool) -> None:
        self.cloud_toggle.setEnabled(ready)
        if not ready:
            self.cloud_toggle.setChecked(False)
        self.ai_status.setText(
            "OpenAI explanations enabled; engine facts remain authoritative."
            if ready
            else "Local coach active. Set OPENAI_API_KEY and OPENAI_MODEL for AI wording."
        )

    @property
    def use_cloud(self) -> bool:
        return self.cloud_toggle.isEnabled() and self.cloud_toggle.isChecked()

    def clear(self) -> None:
        self.bundle = None
        self.current_ply = 0
        self.analyze_button.setText("Analyze Full Game")
        self.report.setText("Run full-game analysis for coaching and accuracy.")
        self.feedback.clear()
        self.practice_button.setEnabled(False)
        self.lessons_button.setEnabled(False)
        self.set_running(False)

    def set_game_context(self, moves: tuple[str, ...]) -> None:
        opening = recognize_opening(moves)
        if opening is None:
            self.opening_summary = "Opening: not identified"
            return
        departure = (
            f" · first move outside this local line: ply {opening.book_plies + 1}"
            if len(moves) > opening.book_plies
            else " · remained in the recognized local line"
        )
        self.opening_summary = f"Opening: {opening.eco} {opening.display_name}{departure}"

    def set_running(self, running: bool) -> None:
        self.analyze_button.setEnabled(not running)
        self.cancel_button.setVisible(running)
        self.progress.setVisible(running)
        if running:
            self.progress.setRange(0, 0)
            self.feedback.setText("Scanning all moves…")

    def set_resumable(self, completed: int, total: int, state: str) -> None:
        self.analyze_button.setText("Resume Analysis")
        self.feedback.setText(
            f"Previous analysis {state} after {completed} of {total} moves. "
            "Resume reuses every completed cached position."
        )

    def set_progress(self, completed: int, total: int, stage: str) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(completed)
        self.progress.setFormat(f"{stage.title()} · %v / %m")

    def set_bundle(self, bundle: CoachBundle, player_color: str, result: str = "*") -> None:
        self.bundle = bundle
        self.analyze_button.setText("Analyze Again")
        self.player_color = player_color
        phases = " · ".join(
            f"{phase.phase.value.title()} {phase.accuracy:.1f}%"
            for phase in bundle.report.phase_summaries
        )
        critical = ", ".join(str(ply) for ply in bundle.report.critical_plies) or "none"
        strongest = ", ".join(str(ply) for ply in bundle.report.strongest_plies) or "none"
        weaknesses = (
            ", ".join(theme.replace("_", " ") for theme in bundle.report.recurring_themes)
            or "none yet"
        )
        opponent_color = "black" if player_color == "white" else "white"
        opponent_accuracy = player_accuracy(bundle.analysis.moves, opponent_color)
        counts = Counter(
            move.classification.value
            for move in bundle.analysis.moves
            if move.mover == player_color
        )
        self.report.setText(
            f"Game Review · Result {result}\n"
            f"Chess Coach accuracy: You {bundle.report.accuracy:.1f}% · "
            f"Opponent {opponent_accuracy:.1f}%\n"
            f"Your moves: {counts['best']} best · {counts['inaccuracy']} inaccuracies · "
            f"{counts['mistake']} mistakes · {counts['blunder']} blunders\n"
            f"{self.opening_summary}\n"
            f"{phases}\nCritical plies: {critical} · "
            f"Strongest plies: {strongest}\nRecurring themes: {weaknesses}"
        )
        self.practice_button.setEnabled(bool(bundle.practice))
        self.lessons_button.setEnabled(bool(bundle.lessons))
        self.set_running(False)
        self.show_ply(self.current_ply)

    def show_ply(self, ply: int) -> None:
        self.current_ply = ply
        if self.bundle is None or ply < 1 or ply > len(self.bundle.analysis.moves):
            self.feedback.setText("")
            return
        move = self.bundle.analysis.moves[ply - 1]
        mode = str(self.filter.currentData())
        critical = move.classification in (
            MoveClassification.INACCURACY,
            MoveClassification.MISTAKE,
            MoveClassification.BLUNDER,
        )
        if (mode == "player" and move.mover != self.player_color) or (
            mode == "critical" and (move.mover != self.player_color or not critical)
        ):
            self.feedback.setText("This move is hidden by the current coach filter.")
            return
        feedback = next((item for item in self.bundle.feedback if item.ply == ply), None)
        if feedback is None:
            self.feedback.setText("No feedback is stored for this move.")
            return
        line = san_variation(move.fen, feedback.continuation) or "—"
        text = f"{feedback.verdict} · {move.accuracy:.1f}%\n{feedback.explanation}"
        if self.verbosity == "detailed":
            text += f"\nLine: {line}\nTakeaway: {feedback.takeaway}"
        self.feedback.setText(text)


class PracticeDialog(QDialog):
    def __init__(
        self, item: PracticeItem, repository: CoachRepository, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.item = item
        self.repository = repository
        self.hint_level = 0
        self.session = TrainingSession(item)
        self.mistake_timer = QTimer(self)
        self.mistake_timer.setSingleShot(True)
        self.mistake_timer.setInterval(700)
        self.mistake_timer.timeout.connect(self._restore_after_mistake)
        self.setWindowTitle(f"Practice · {item.theme.replace('_', ' ').title()}")
        layout = QVBoxLayout(self)
        self.prompt = QLabel("Find the best move.")
        self.prompt.setWordWrap(True)
        layout.addWidget(self.prompt)
        self.game = self.session.game
        self.board = ChessBoard(self.game)
        self.board.set_orientation(self.game.turn)
        self.board.game_changed.connect(self._attempted)
        layout.addWidget(self.board)
        controls = QHBoxLayout()
        self.hint_button = QPushButton("Hint")
        self.reveal_button = QPushButton("Reveal Solution")
        close_button = QPushButton("Close")
        controls.addWidget(self.hint_button)
        controls.addWidget(self.reveal_button)
        controls.addWidget(close_button)
        layout.addLayout(controls)
        self.hint_button.clicked.connect(self._hint)
        self.reveal_button.clicked.connect(self._reveal)
        close_button.clicked.connect(self.reject)
        self.resize(620, 680)

    def _attempted(self) -> None:
        move = self.game.position.move_stack[-1]
        result = self.session.attempt(move)
        if result.mistake:
            self.item = self.repository.record_practice_attempt(self.item, move.uci(), False)
            self.prompt.setText(result.feedback)
            self.board.set_review_moves(move, None)
            self.board.set_classification("Mistake", "#b42318")
            self.board.input_allowed = False
            self.mistake_timer.start()
            return
        self.game = self.session.game
        self.board.game = self.game
        self.board.clear_selection()
        if result.completed:
            self.item = self.repository.record_practice_attempt(self.item, move.uci(), True)
            self.prompt.setText("Correct. This position has been scheduled for later review.")
            self.board.input_allowed = False
        else:
            self.prompt.setText(result.feedback)

    def _restore_after_mistake(self) -> None:
        self.game = self.session.game
        self.board.game = self.game
        self.board.set_review_moves(None, None)
        self.board.set_classification("")
        self.board.input_allowed = True
        self.board.clear_selection()

    def _hint(self) -> None:
        self.hint_level = min(self.hint_level + 1, 3)
        board = chess.Board(self.item.fen)
        remaining = self.session.remaining_solution
        first = chess.Move.from_uci(remaining[0])
        hints = (
            f"Theme: {self.item.theme.replace('_', ' ')}.",
            f"Candidate move: {board.san(first)}.",
            f"Engine line: {san_variation(board.fen(), remaining)}",
        )
        self.prompt.setText(hints[self.hint_level - 1])

    def _reveal(self) -> None:
        self.prompt.setText(f"Solution: {san_variation(self.item.fen, self.item.solution)}")
        self.board.input_allowed = False


class LessonsDialog(QDialog):
    def __init__(
        self,
        lessons: tuple[Lesson, ...],
        repository: CoachRepository,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.lessons = lessons
        self.repository = repository
        self.completed_ids = {lesson.id for lesson in lessons if lesson.completed}
        self.step = 0
        self.setWindowTitle("Personalized Lessons")
        layout = QVBoxLayout(self)
        self.selector = QComboBox()
        for lesson in lessons:
            self.selector.addItem(lesson.title)
        self.content = QLabel()
        self.content.setWordWrap(True)
        self.example_game = Game()
        self.example_board = ChessBoard(self.example_game)
        self.example_board.input_allowed = False
        self.example_board.hide()
        navigation = QHBoxLayout()
        self.previous = QPushButton("Previous Step")
        self.next = QPushButton("Next Step")
        self.practice = QPushButton("Practice Concept")
        complete = QPushButton("Mark Complete")
        close = QPushButton("Close")
        layout.addWidget(self.selector)
        layout.addWidget(self.content)
        layout.addWidget(self.example_board)
        navigation.addWidget(self.previous)
        navigation.addWidget(self.next)
        navigation.addWidget(self.practice)
        layout.addLayout(navigation)
        layout.addWidget(complete)
        layout.addWidget(close)
        self.selector.currentIndexChanged.connect(self._load_lesson)
        self.previous.clicked.connect(lambda: self._change_step(-1))
        self.next.clicked.connect(lambda: self._change_step(1))
        self.practice.clicked.connect(self._practice)
        complete.clicked.connect(self._complete)
        close.clicked.connect(self.accept)
        self._load_lesson(0)
        self.resize(680, 700)

    def _load_lesson(self, index: int) -> None:
        if not 0 <= index < len(self.lessons):
            return
        self.step = min(4, self.repository.lesson_step(self.lessons[index].id))
        self._show_step()

    def _show_step(self) -> None:
        index = self.selector.currentIndex()
        if not 0 <= index < len(self.lessons):
            return
        lesson = self.lessons[index]
        cues = "\n• ".join(lesson.recognition_cues)
        steps = (
            f"1 of 5 · Idea\n\n{lesson.concept}",
            f"2 of 5 · Recognition cues\n\n• {cues}",
            f"3 of 5 · Example\n\nMove {lesson.example_ply} from game "
            f"{lesson.example_game_id[:8]}. Find the relevant pieces on the board.",
            f"4 of 5 · Common error\n\n{lesson.common_error}\n\n"
            "Use Practice Concept to solve the engine-verified source position.",
            "5 of 5 · Recap\n\nName the cue you will check in your next game, then mark "
            "the lesson complete. Later successful practice reduces this weakness score.",
        )
        self.content.setText(steps[self.step])
        self.example_board.setVisible(self.step == 2 and self._set_example_position(lesson))
        self.previous.setEnabled(self.step > 0)
        self.next.setEnabled(self.step < 4)
        self.practice.setEnabled(bool(lesson.exercise_ids))

    def _set_example_position(self, lesson: Lesson) -> bool:
        data = GameDatabase(self.repository.path).load_game(lesson.example_game_id)
        if data is None or lesson.example_ply < 1 or lesson.example_ply >= len(data.fens):
            return False
        self.example_game = Game(data.fens[lesson.example_ply - 1])
        self.example_board.game = self.example_game
        self.example_board.set_orientation(self.example_game.turn)
        self.example_board.refresh()
        return True

    def _change_step(self, amount: int) -> None:
        index = self.selector.currentIndex()
        if not 0 <= index < len(self.lessons):
            return
        self.step = max(0, min(4, self.step + amount))
        lesson = self.lessons[index]
        self.repository.set_lesson_completed(
            lesson.id, lesson.id in self.completed_ids, step=self.step
        )
        self._show_step()

    def _practice(self) -> None:
        index = self.selector.currentIndex()
        if not 0 <= index < len(self.lessons):
            return
        lesson = self.lessons[index]
        items = {item.id: item for item in self.repository.practice_items()}
        item = next((items[item_id] for item_id in lesson.exercise_ids if item_id in items), None)
        if item is not None:
            PracticeDialog(item, self.repository, self).exec()

    def _complete(self) -> None:
        index = self.selector.currentIndex()
        if 0 <= index < len(self.lessons):
            self.completed_ids.add(self.lessons[index].id)
            self.repository.set_lesson_completed(self.lessons[index].id, step=4)
            self.content.setText(
                self.content.text() + "\n\nCompleted. Continue with follow-up practice."
            )
