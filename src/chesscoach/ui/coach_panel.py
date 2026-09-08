"""Full-game coaching summary, filters, practice, and lesson entry points."""

import chess
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
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
from chesscoach.coach.models import CoachBundle, Lesson, MoveClassification, PracticeItem
from chesscoach.storage.coach import CoachRepository
from chesscoach.ui.chess_board import ChessBoard


class CoachPanel(QWidget):
    analyze_requested = Signal()
    cancel_requested = Signal()
    practice_requested = Signal()
    lessons_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bundle: CoachBundle | None = None
        self.player_color = "white"
        self.current_ply = 0
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
        self.filter = QComboBox()
        self.filter.addItem("My moves", "player")
        self.filter.addItem("Mistakes and blunders", "critical")
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
        self.practice_button.setEnabled(False)
        self.lessons_button.setEnabled(False)
        learning.addWidget(self.practice_button)
        learning.addWidget(self.lessons_button)
        layout.addLayout(learning)
        self.analyze_button.clicked.connect(self.analyze_requested.emit)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        self.practice_button.clicked.connect(self.practice_requested.emit)
        self.lessons_button.clicked.connect(self.lessons_requested.emit)
        self.filter.currentIndexChanged.connect(lambda: self.show_ply(self.current_ply))

    def set_ai_ready(self, ready: bool) -> None:
        self.ai_status.setText(
            "OpenAI explanations enabled; engine facts remain authoritative."
            if ready
            else "Local coach active. Set OPENAI_API_KEY and OPENAI_MODEL for AI wording."
        )

    def clear(self) -> None:
        self.bundle = None
        self.current_ply = 0
        self.report.setText("Run full-game analysis for coaching and accuracy.")
        self.feedback.clear()
        self.practice_button.setEnabled(False)
        self.lessons_button.setEnabled(False)
        self.set_running(False)

    def set_running(self, running: bool) -> None:
        self.analyze_button.setEnabled(not running)
        self.cancel_button.setVisible(running)
        self.progress.setVisible(running)
        if running:
            self.progress.setRange(0, 0)
            self.feedback.setText("Scanning all moves…")

    def set_progress(self, completed: int, total: int, stage: str) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(completed)
        self.progress.setFormat(f"{stage.title()} · %v / %m")

    def set_bundle(self, bundle: CoachBundle, player_color: str) -> None:
        self.bundle = bundle
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
        self.report.setText(
            f"{bundle.report.summary}\n{phases}\nCritical plies: {critical} · "
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
        line = " ".join(feedback.continuation) or "—"
        self.feedback.setText(
            f"{feedback.verdict} · {move.accuracy:.1f}%\n"
            f"{feedback.explanation}\nLine: {line}\nTakeaway: {feedback.takeaway}"
        )


class PracticeDialog(QDialog):
    def __init__(
        self, item: PracticeItem, repository: CoachRepository, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.item = item
        self.repository = repository
        self.hint_level = 0
        self.setWindowTitle(f"Practice · {item.theme.replace('_', ' ').title()}")
        layout = QVBoxLayout(self)
        self.prompt = QLabel("Find the best move.")
        self.prompt.setWordWrap(True)
        layout.addWidget(self.prompt)
        self.game = Game(item.fen)
        self.board = ChessBoard(self.game)
        self.board.set_orientation(self.game.turn)
        self.board.game_changed.connect(self._attempted)
        layout.addWidget(self.board)
        controls = QHBoxLayout()
        self.hint_button = QPushButton("Hint")
        close_button = QPushButton("Close")
        controls.addWidget(self.hint_button)
        controls.addWidget(close_button)
        layout.addLayout(controls)
        self.hint_button.clicked.connect(self._hint)
        close_button.clicked.connect(self.reject)
        self.resize(620, 680)

    def _attempted(self) -> None:
        move = self.game.position.move_stack[-1]
        successful = self.item.validate_attempt(move)
        self.item = self.repository.record_practice_attempt(self.item, move.uci(), successful)
        if successful:
            self.prompt.setText("Correct. This position has been scheduled for later review.")
            self.board.input_allowed = False
        else:
            self.prompt.setText("Try again. Check forcing moves before committing.")
            self.game = Game(self.item.fen)
            self.board.game = self.game
            self.board.clear_selection()

    def _hint(self) -> None:
        self.hint_level = min(self.hint_level + 1, 3)
        board = chess.Board(self.item.fen)
        first = chess.Move.from_uci(self.item.solution[0])
        hints = (
            f"Theme: {self.item.theme.replace('_', ' ')}.",
            f"Candidate move: {board.san(first)}.",
            f"Engine line: {_san_line(board, self.item.solution)}",
        )
        self.prompt.setText(hints[self.hint_level - 1])


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
        self.setWindowTitle("Personalized Lessons")
        layout = QVBoxLayout(self)
        self.selector = QComboBox()
        for lesson in lessons:
            self.selector.addItem(lesson.title)
        self.content = QLabel()
        self.content.setWordWrap(True)
        complete = QPushButton("Mark Complete")
        close = QPushButton("Close")
        layout.addWidget(self.selector)
        layout.addWidget(self.content)
        layout.addWidget(complete)
        layout.addWidget(close)
        self.selector.currentIndexChanged.connect(self._show_lesson)
        complete.clicked.connect(self._complete)
        close.clicked.connect(self.accept)
        self._show_lesson(0)
        self.resize(500, 360)

    def _show_lesson(self, index: int) -> None:
        if not 0 <= index < len(self.lessons):
            return
        lesson = self.lessons[index]
        cues = "\n• ".join(lesson.recognition_cues)
        self.content.setText(
            f"{lesson.concept}\n\nRecognition cues:\n• {cues}\n\n"
            f"Common error: {lesson.common_error}\n"
            f"Example: move {lesson.example_ply} from game {lesson.example_game_id}"
        )

    def _complete(self) -> None:
        index = self.selector.currentIndex()
        if 0 <= index < len(self.lessons):
            self.repository.set_lesson_completed(self.lessons[index].id)
            self.content.setText(self.content.text() + "\n\nCompleted.")


def _san_line(board: chess.Board, moves: tuple[str, ...]) -> str:
    san = []
    for uci in moves:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        san.append(board.san(move))
        board.push(move)
    return " ".join(san)
