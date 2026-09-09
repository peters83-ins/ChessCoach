"""Match setup, human/engine turns, and explicit persistence feedback."""

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import chess
from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from chesscoach import __version__
from chesscoach.chess.game import Game
from chesscoach.chess.pgn import export_pgn, san_variation
from chesscoach.chess.review import ReviewSession
from chesscoach.coach.models import AnalysisProgress, CoachBundle, MoveAnalysis
from chesscoach.coach.pipeline import CoachPipeline
from chesscoach.coach.scoring import pov_score
from chesscoach.coach.worker import CoachRunner
from chesscoach.config import Settings
from chesscoach.courses.catalog import CourseCatalog
from chesscoach.engine.analysis import PositionAnalysis
from chesscoach.engine.worker import EngineRunner, SearchResult
from chesscoach.preferences import UserPreferences
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameData, GameDatabase
from chesscoach.storage.match import BotMatch
from chesscoach.ui.chess_board import ChessBoard
from chesscoach.ui.coach_panel import CoachPanel, LessonsDialog
from chesscoach.ui.course_center import CourseDetailDialog, CourseLibraryDialog
from chesscoach.ui.diagnostics import DiagnosticInfo, DiagnosticsDialog
from chesscoach.ui.evaluation_bar import EvaluationBar
from chesscoach.ui.first_run import FirstRunWizard
from chesscoach.ui.game_review import GameReview
from chesscoach.ui.learning_center import PracticeQueueDialog, WeaknessDashboardDialog
from chesscoach.ui.learning_home import LearningHomeDialog
from chesscoach.ui.match_setup import MatchSetup
from chesscoach.ui.move_history import BADGES, MoveHistory
from chesscoach.ui.saved_games import SavedGamesDialog
from chesscoach.ui.settings_dialog import SettingsDialog
from chesscoach.ui.theme import MODERN_STYLESHEET


class MainWindow(QMainWindow):
    def __init__(
        self,
        game: Game | None = None,
        *,
        database: GameDatabase | None = None,
        runner: EngineRunner | None = None,
        coach_runner: CoachRunner | None = None,
        preference_settings: QSettings | None = None,
        course_catalog: CourseCatalog | None = None,
    ) -> None:
        super().__init__()
        self.setStyleSheet(MODERN_STYLESHEET)
        self.game = game if game is not None else Game()
        self.active = game is not None
        self.match: BotMatch | None = None
        self.engine_path = ""
        self.engine_signature = ""
        self.engine_failed = False
        self.last_error = ""
        self.review_details = ""
        self.review: ReviewSession | None = None
        self.review_cache: dict[str, PositionAnalysis] = {}
        self.coach_bundle: CoachBundle | None = None
        self.coach_running = False
        self.retry_ply: int | None = None
        self.retry_hint_level = 0
        self.line_games: list[Game] = []
        self.line_step = 0
        self.pending_bot_result: SearchResult | None = None
        self.pending_bot_fen = ""
        self.pending_bot_match_id = ""
        self.bot_move_timer = QTimer(self)
        self.bot_move_timer.setSingleShot(True)
        self.bot_move_timer.timeout.connect(self.apply_pending_bot_move)
        self.review_timer = QTimer(self)
        self.review_timer.setSingleShot(True)
        self.review_timer.setInterval(150)
        self.review_timer.timeout.connect(self.analyze_review_position)
        self.line_timer = QTimer(self)
        self.line_timer.setInterval(650)
        self.line_timer.timeout.connect(self.advance_best_line)
        self.runner = runner if runner is not None else EngineRunner(self)
        self.runner.result.connect(self.engine_result)
        self.runner.error.connect(self.engine_error)
        data_dir = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
        )
        self.database = database or GameDatabase(
            data_dir / "games" / "games.sqlite3",
            legacy_path=data_dir / "games.sqlite3",
        )
        self.coach_repository = CoachRepository(self.database.path)
        self.coach_runner = coach_runner or CoachRunner(self)
        self.coach_runner.progress.connect(self.coach_progress)
        self.coach_runner.result.connect(self.coach_result)
        self.coach_runner.error.connect(self.coach_error)
        self.coach_settings = Settings.from_environment(Path(".env"))
        self.preference_settings = preference_settings or QSettings()
        self.preferences = UserPreferences.load(self.preference_settings)
        self.course_catalog = course_catalog or CourseCatalog.built_in()
        self.first_run_wizard: FirstRunWizard | None = None
        self.destination_dialogs: dict[str, QDialog] = {}
        self.setWindowTitle("Chess Coach")
        self.resize(1050, 740)
        navigation = QToolBar("Navigation", self)
        navigation.setMovable(False)
        navigation.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(navigation)
        self.play_action = QAction("Play", self)
        self.games_action = QAction("Games", self)
        self.review_action = QAction("Review", self)
        self.practice_action = QAction("Practice", self)
        self.lessons_action = QAction("Lessons", self)
        self.courses_action = QAction("Courses", self)
        self.learn_action = QAction("Learn", self)
        self.lessons_action.setToolTip("Personalized lessons generated from your analyzed games")
        self.courses_action.setToolTip("Reviewed offline opening courses")
        self.learn_action.setToolTip("Your recommended next learning activity")
        self.settings_action = QAction("Settings", self)
        self.play_action.setShortcut(QKeySequence.StandardKey.New)
        self.games_action.setShortcut(QKeySequence.StandardKey.Open)
        self.review_action.setShortcut(QKeySequence("Ctrl+R"))
        self.practice_action.setShortcut(QKeySequence("Ctrl+P"))
        self.lessons_action.setShortcut(QKeySequence("Ctrl+L"))
        self.courses_action.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.learn_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        for action in (
            self.play_action,
            self.games_action,
            self.review_action,
            self.practice_action,
            self.lessons_action,
            self.courses_action,
            self.learn_action,
            self.settings_action,
        ):
            navigation.addAction(action)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        board_area = QWidget()
        board_layout = QHBoxLayout(board_area)
        board_layout.setContentsMargins(0, 0, 0, 0)
        board_layout.setSpacing(5)
        self.evaluation_bar = EvaluationBar()
        board_layout.addWidget(self.evaluation_bar)
        self.board = ChessBoard(self.game)
        board_layout.addWidget(self.board, 1)
        layout.addWidget(board_area, 2)
        sidebar_container = QWidget()
        sidebar_container.setMinimumWidth(340)
        sidebar = QVBoxLayout(sidebar_container)
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setWidget(sidebar_container)
        layout.addWidget(sidebar_scroll, 1)
        title = QLabel("Chess Coach")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        sidebar.addWidget(title)
        self.setup = MatchSetup()
        self.setup.start_requested.connect(self.start_match)
        sidebar.addWidget(self.setup)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        sidebar.addWidget(self.status_label)
        help_text = QLabel("Select a piece, then a highlighted destination.")
        help_text.setWordWrap(True)
        sidebar.addWidget(help_text)
        self.attack_toggle = QCheckBox("Show attacks on enemy pieces")
        self.attack_toggle.setToolTip(
            "Geometric attacks, including pinned pieces; not necessarily legal captures."
        )
        self.attack_toggle.toggled.connect(self.board.set_attacks_visible)
        sidebar.addWidget(self.attack_toggle)
        self.review_panel = GameReview()
        self.review_panel.index_changed.connect(self.set_review_index)
        self.review_panel.show_line_requested.connect(self.toggle_best_line)
        self.review_panel.retry_requested.connect(self.toggle_retry_move)
        self.review_panel.hint_requested.connect(self.show_retry_hint)
        self.review_panel.hide()
        sidebar.addWidget(self.review_panel)
        self.coach_panel = CoachPanel()
        self.coach_panel.hide()
        self.coach_panel.set_ai_ready(
            bool(self.coach_settings.openai_api_key and self.coach_settings.openai_model)
        )
        self.coach_panel.analyze_requested.connect(self.start_coach_analysis)
        self.coach_panel.cancel_requested.connect(self.cancel_coach_analysis)
        self.coach_panel.practice_requested.connect(self.open_practice)
        self.coach_panel.lessons_requested.connect(self.open_lessons)
        self.coach_panel.weaknesses_requested.connect(self.open_weaknesses)
        sidebar.addWidget(self.coach_panel)
        self.engine_label = QLabel("")
        self.engine_label.setWordWrap(True)
        sidebar.addWidget(self.engine_label)
        self.history = MoveHistory()
        self.history.move_selected.connect(self.set_review_index)
        sidebar.addWidget(self.history, 1)
        self.storage_label = QLabel(f"Saved games: {self.database.path}")
        self.storage_label.setWordWrap(True)
        self.storage_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sidebar.addWidget(self.storage_label)
        self.new_game_button = QPushButton("New Game")
        self.undo_button = QPushButton("Undo")
        self.claim_draw_button = QPushButton("Claim Draw")
        self.copy_pgn_button = QPushButton("Copy PGN")
        self.save_button = QPushButton("Save Match")
        self.save_button.setToolTip(str(self.database.path))
        self.load_button = QPushButton("Load Saved Game")
        self.retry_button = QPushButton("Retry Engine")
        self.review_game_button = QPushButton("Review Game")
        self.review_game_button.hide()
        self.settings_button = QPushButton("Settings")
        self.diagnostics_button = QPushButton("Diagnostics")
        for button in (self.new_game_button, self.save_button, self.review_game_button):
            button.setObjectName("primaryAction")
        for button in (
            self.new_game_button,
            self.undo_button,
            self.claim_draw_button,
            self.copy_pgn_button,
            self.save_button,
            self.load_button,
            self.retry_button,
            self.review_game_button,
            self.settings_button,
            self.diagnostics_button,
        ):
            sidebar.addWidget(button)
        self.new_game_button.clicked.connect(self.new_game)
        self.undo_button.clicked.connect(self.undo)
        self.claim_draw_button.clicked.connect(self.claim_draw)
        self.copy_pgn_button.clicked.connect(self.copy_pgn)
        self.save_button.clicked.connect(self.save_match)
        self.load_button.clicked.connect(self.load_saved_game)
        self.retry_button.clicked.connect(self.retry_engine)
        self.review_game_button.clicked.connect(self.review_current_game)
        self.settings_button.clicked.connect(self.open_settings)
        self.diagnostics_button.clicked.connect(self.open_diagnostics)
        self.board.game_changed.connect(self.position_changed)
        self.board.message.connect(self.show_board_message)
        self.play_action.triggered.connect(self.new_game)
        self.games_action.triggered.connect(self.load_saved_game)
        self.review_action.triggered.connect(self.open_review_destination)
        self.practice_action.triggered.connect(self.open_practice)
        self.lessons_action.triggered.connect(self.open_lessons)
        self.courses_action.triggered.connect(self.open_courses)
        self.learn_action.triggered.connect(self.open_learning_home)
        self.settings_action.triggered.connect(self.open_settings)
        self.apply_preferences(self.preferences)
        self.refresh()

    def show_board_message(self, message: str) -> None:
        self.statusBar().showMessage(message)
        if not self.active and not self.review_details:
            self.status_label.setText(message)

    def maybe_show_first_run(self) -> None:
        if not QSettings().value("setup/complete", False, bool):
            self.open_first_run()

    def open_first_run(self) -> None:
        wizard = FirstRunWizard(self.coach_settings, self.database.path, parent=self)
        wizard.settings_saved.connect(self.apply_settings)
        wizard.finished.connect(lambda: setattr(self, "first_run_wizard", None))
        self.first_run_wizard = wizard
        wizard.open()

    def open_settings(self) -> None:
        dialog = SettingsDialog(
            self.coach_settings,
            preferences=self.preferences,
            preference_settings=self.preference_settings,
            parent=self,
        )
        dialog.settings_saved.connect(self.apply_settings)
        dialog.preferences_saved.connect(self.apply_preferences)
        dialog.exec()

    def apply_settings(self, settings: Settings) -> None:
        self.coach_settings = settings
        if settings.stockfish_path:
            self.setup.engine_path.setText(settings.stockfish_path)
        self.coach_panel.set_ai_ready(bool(settings.openai_api_key and settings.openai_model))
        self.statusBar().showMessage("Settings saved locally.", 4000)

    def apply_preferences(self, preferences: UserPreferences) -> None:
        self.preferences = preferences
        self.board.set_appearance(preferences.board_theme, preferences.piece_scale)
        self.coach_panel.set_preferences(
            preferences.review_perspective, preferences.coach_verbosity
        )
        point_size = round(10 * preferences.text_scale / 100)
        central = self.centralWidget()
        if central is not None:
            central.setStyleSheet(f"font-size: {point_size}pt;")
        if self.review is not None:
            self._apply_review_orientation(self.review.data.player_color)
            self.set_review_index(self.review.index)

    def _apply_review_orientation(self, player_color: str) -> None:
        preference = self.preferences.board_orientation
        color = player_color == "white" if preference == "player" else preference == "white"
        self.board.set_orientation(color)
        self.evaluation_bar.set_orientation(color)

    def open_diagnostics(self) -> None:
        ai_ready = bool(self.coach_settings.openai_api_key and self.coach_settings.openai_model)
        info = DiagnosticInfo(
            __version__,
            str(self.database.path),
            self.setup.engine_path.text().strip(),
            self.engine_signature,
            ai_ready,
            self.last_error,
        )
        DiagnosticsDialog(
            info,
            secret=self.coach_settings.openai_api_key,
            parent=self,
        ).exec()

    def refresh(self) -> None:
        status = self.game.status()
        self.status_label.setText(
            self.review_details
            if self.review_details
            else status.message
            if self.active
            else "Choose color and difficulty, then Start Match."
        )
        self.history.set_moves(self.review.history if self.review else self.game.history())
        if self.coach_bundle is not None:
            self.history.set_classifications(self.coach_bundle.analysis.moves)
        human_turn = self.match is None or self.game.turn == self.match.player_color
        self.board.input_allowed = self.active and human_turn
        self.board.preview_only = not self.active
        self.board.input_message = (
            "Preview only. Click Start Match to play, or choose Local two-player without an engine."
            if not self.active
            else "Wait for the computer to move."
        )
        can_undo = self.game.can_undo
        if self.match is not None:
            can_undo = not status.game_over and len(self.game.history()) > (
                0 if self.match.player_color else 1
            )
        self.undo_button.setEnabled(self.active and can_undo)
        self.claim_draw_button.setEnabled(self.active and human_turn and status.can_claim_draw)
        self.save_button.setEnabled(self.match is not None and bool(self.game.history()))
        self.load_button.setEnabled(not self.active)
        self.retry_button.setEnabled(
            self.engine_failed
            and ((self.match is not None and not status.game_over) or self.review is not None)
        )
        self.review_game_button.setVisible(
            self.match is not None and status.game_over and bool(self.game.history())
        )
        self.board.refresh()

    def start_match(self) -> None:
        bot = self.setup.mode.currentIndex() == 0
        path = self.setup.engine_path.text().strip()
        if bot and not path:
            self.statusBar().showMessage(
                "Select a Stockfish executable first, or choose Local two-player."
            )
            return
        if not self.save_match():
            return
        self.runner.cancel()
        self.cancel_pending_bot()
        self.game.reset()
        self.active = True
        self.engine_failed = False
        self.review_details = ""
        self.review = None
        self.review_cache.clear()
        self.coach_bundle = None
        self.coach_running = False
        self.coach_runner.cancel()
        self.review_timer.stop()
        self.line_timer.stop()
        self.retry_ply = None
        self.review_panel.hide()
        self.coach_panel.clear()
        self.coach_panel.hide()
        self.board.set_review_moves(None, None)
        self.evaluation_bar.clear()
        self.engine_path = path
        self.match = (
            BotMatch(
                self.game,
                bool(self.setup.color.currentData()),
                int(self.setup.difficulty.currentData()),
            )
            if bot
            else None
        )
        self.board.set_orientation(self.match.player_color if self.match else chess.WHITE)
        self.evaluation_bar.set_orientation(self.match.player_color if self.match else chess.WHITE)
        self.setup.setEnabled(False)
        self.statusBar().clearMessage()
        self.engine_label.clear()
        self.refresh()
        self.request_engine()

    def position_changed(self) -> None:
        if self.retry_ply is not None:
            self.handle_retry_attempt()
            return
        if self.match is not None:
            self.match.record_position()
            if self.game.position.move_stack:
                self.board.set_review_moves(self.game.position.move_stack[-1], None)
        self.refresh()
        if self.game.status().game_over:
            self.runner.cancel()
            self.engine_label.clear()
            outcome = self.game.position.outcome()
            self.evaluation_bar.set_result(outcome.winner if outcome else None)
            self.save_match()
            self.statusBar().showMessage("Game saved. Choose Review Game to learn from it.")
        else:
            self.request_engine()

    def request_engine(self) -> None:
        if self.match is None or not self.active or self.game.status().game_over:
            return
        self.engine_failed = False
        self.evaluation_bar.clear()
        self.engine_label.setText("Stockfish is thinking…")
        self.runner.search(
            self.game.position,
            self.engine_path,
            self.match.elo,
            self.game.turn != self.match.player_color,
        )
        self.refresh()

    def cancel_pending_bot(self) -> None:
        self.bot_move_timer.stop()
        self.pending_bot_result = None
        self.pending_bot_fen = ""
        self.pending_bot_match_id = ""

    def engine_result(self, result: SearchResult) -> None:
        self.engine_signature = result.engine_signature
        if self.review is not None:
            self.review_cache[result.analysis.fen] = result.analysis
            position = self.review.analysis_position(self.review.index)
            if position is not None and position.fen() == result.analysis.fen:
                self.show_review_analysis(result.analysis)
            return
        if self.match is None or not self.active or result.analysis.fen != self.game.fen:
            return
        self.match.elo = result.actual_elo
        if result.move is not None:
            if self.game.turn == self.match.player_color or result.analysis.fen != self.game.fen:
                self.engine_error("Stockfish returned a move for the wrong position. Retry Engine.")
                return
            self.pending_bot_result = result
            self.pending_bot_fen = self.game.fen
            self.pending_bot_match_id = self.match.id
            self.engine_label.setText("Stockfish is ready…")
            if self.preferences.bot_move_delay_ms == 0:
                self.apply_pending_bot_move()
            else:
                self.bot_move_timer.start(self.preferences.bot_move_delay_ms)
            self.refresh()
            return
        candidate = result.analysis.candidates[0]
        score = candidate.score.white()
        self.evaluation_bar.set_score(candidate.score)
        mate = score.mate()
        evaluation = f"Mate {mate:+d}" if mate is not None else f"{(score.score() or 0) / 100:+.2f}"
        best = (
            self.game.position.san(result.analysis.best_move) if result.analysis.best_move else "—"
        )
        self.engine_label.setText(
            f"White eval: {evaluation} · Best: {best}\nBot: ~{result.actual_elo} "
            + (
                "practice level (uncalibrated)"
                if result.actual_elo in (800, 1000, 1200)
                else "Elo target"
            )
        )
        self.refresh()

    def apply_pending_bot_move(self) -> None:
        result = self.pending_bot_result
        expected_fen = self.pending_bot_fen
        expected_match_id = self.pending_bot_match_id
        self.cancel_pending_bot()
        if (
            result is None
            or result.move is None
            or self.match is None
            or self.match.id != expected_match_id
            or not self.active
            or self.game.status().game_over
            or self.game.turn == self.match.player_color
            or self.game.fen != expected_fen
        ):
            return
        if not self.game.attempt_move(result.move):
            self.engine_error("Stockfish returned a move for the wrong position. Retry Engine.")
            return
        self.board.clear_selection()
        self.position_changed()

    def engine_error(self, message: str) -> None:
        self.last_error = message
        self.engine_failed = True
        self.engine_label.setText(message)
        self.evaluation_bar.clear()
        if self.review is not None:
            self.review_panel.best_label.setText("Engine best: Analysis failed")
            self.review_panel.evaluation_label.setText("Evaluation before move: —")
        self.refresh()

    def retry_engine(self) -> None:
        if self.review is not None:
            self.analyze_review_position()
        else:
            self.request_engine()

    def save_match(self) -> bool:
        if self.match is None or not self.game.history():
            return True
        result = self.match.save(self.database)
        if not result.success:
            self.statusBar().showMessage(f"Save failed: {result.error}")
            return False
        self.statusBar().showMessage("Game saved.")
        return True

    def load_saved_game(self) -> None:
        if not self.save_match():
            return
        try:
            games = self.database.list_games()
        except (OSError, sqlite3.Error, ValueError) as error:
            self.statusBar().showMessage(f"Load failed: {error}")
            return
        if not games:
            self.statusBar().showMessage(f"No saved games found in {self.database.path.parent}")
            return
        statuses = self.coach_repository.game_learning_statuses(tuple(game.id for game in games))
        games = tuple(
            replace(
                game,
                analyzed=status.analyzed if status is not None else False,
                practice_count=status.practice_count if status is not None else 0,
            )
            for game in games
            for status in (statuses.get(game.id),)
        )
        dialog = SavedGamesDialog(
            games,
            str(self.database.path),
            self,
            delete_game=self.delete_saved_game,
            export_game=self.export_saved_game,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        game_id = dialog.selected_game_id()
        if game_id is None:
            return
        try:
            data = self.database.load_game(game_id)
        except (OSError, sqlite3.Error, ValueError) as error:
            self.statusBar().showMessage(f"Load failed: {error}")
            return
        if data is None:
            self.statusBar().showMessage("Load failed: game no longer exists.")
            return
        self.open_review(data)

    def open_review_destination(self) -> None:
        if self.review is not None:
            self.review_panel.setFocus()
        elif self.match is not None and self.game.status().game_over:
            self.review_current_game()
        else:
            self.load_saved_game()

    def delete_saved_game(self, game_id: str) -> bool:
        try:
            deleted = self.database.delete_game(game_id)
            if deleted:
                self.coach_repository.delete_game_learning(game_id)
        except (OSError, sqlite3.Error, ValueError) as error:
            self.statusBar().showMessage(f"Delete failed: {error}")
            return False
        self.statusBar().showMessage("Saved game deleted." if deleted else "Game not found.")
        return deleted

    def export_saved_game(self, game_id: str, path: Path) -> bool:
        try:
            data = self.database.load_game(game_id)
            if data is None:
                raise ValueError("Game not found.")
            path.write_text(data.pgn, encoding="utf-8")
        except (OSError, sqlite3.Error, ValueError) as error:
            self.statusBar().showMessage(f"Export failed: {error}")
            return False
        self.statusBar().showMessage(f"PGN exported to {path}")
        return True

    def open_review(self, data: GameData, *, auto_analyze: bool = False) -> None:
        """Open validated saved data in the reusable review workspace."""
        try:
            review = ReviewSession(data)
        except ValueError as error:
            self.statusBar().showMessage(f"Load failed: {error}")
            return
        self.runner.cancel()
        self.cancel_pending_bot()
        self.match = None
        self.active = False
        self.review = review
        self.review_cache.clear()
        self.coach_bundle = CoachPipeline(self.coach_repository).load(data)
        self.coach_panel.clear()
        self.coach_panel.set_game_context(data.moves)
        self.review_details = (
            f"Saved game for analysis · Player {data.player_color.title()} · "
            f"Bot {data.bot_elo} · Result {data.result}"
        )
        self.setup.setEnabled(False)
        self.setup.hide()
        self._apply_review_orientation(data.player_color)
        self.review_panel.show()
        self.coach_panel.show()
        resumable = None
        if self.coach_bundle is not None:
            self.coach_panel.set_bundle(self.coach_bundle, data.player_color, data.result)
            self.review_panel.set_analysis(self.coach_bundle.analysis, data.player_color)
        else:
            self.review_panel.set_analysis(None, data.player_color)
            resumable = self.coach_repository.latest_run_status(data.id)
        self.review_panel.configure(review.total)
        self.set_review_index(0 if auto_analyze else review.total)
        if resumable is not None and resumable.state != "complete":
            self.coach_panel.set_resumable(resumable.completed, resumable.total, resumable.state)
        self.statusBar().showMessage("Saved game loaded for review.")
        if auto_analyze:
            self.start_coach_analysis()

    def review_current_game(self) -> None:
        """Save a completed match and enter guided review in one action."""
        if self.match is None or not self.game.status().game_over:
            return
        match_id = self.match.id
        if not self.save_match():
            return
        try:
            data = self.database.load_game(match_id)
        except (OSError, sqlite3.Error, ValueError) as error:
            self.statusBar().showMessage(f"Review failed: {error}")
            return
        if data is None:
            self.statusBar().showMessage("Review failed: the saved game could not be reopened.")
            return
        self.open_review(data, auto_analyze=True)

    def set_review_index(self, index: int) -> None:
        if self.review is None:
            return
        if self.retry_ply is not None:
            return
        self.stop_best_line()
        self.runner.cancel()
        self.cancel_pending_bot()
        self.review_timer.stop()
        self.engine_failed = False
        self.game = self.review.game_at(index)
        self.board.game = self.game
        self.review_panel.set_index(index)
        self.coach_panel.show_ply(index)
        played = self.review.played_at(index)
        move = played[0] if played else None
        played_text = (
            f"{played[1].number}.{'..' if played[1].color == chess.BLACK else ''} "
            f"{played[1].san} ({'Black' if played[1].color == chess.BLACK else 'White'})"
            if played
            else "—"
        )
        self.board.set_review_moves(move, None)
        self.board.set_classification("")
        self.evaluation_bar.clear()
        self.review_panel.set_details(played_text, "—", "—")
        self.engine_label.clear()
        self.refresh()
        position = self.review.analysis_position(index)
        if position is None:
            return
        if self.coach_bundle is not None and index <= len(self.coach_bundle.analysis.moves):
            analyzed = self.coach_bundle.analysis.moves[index - 1]
            if analyzed.fen == position.fen():
                self.show_coach_move(analyzed)
                return
        if self.coach_running:
            return
        cached = self.review_cache.get(position.fen())
        if cached is not None:
            self.show_review_analysis(cached)
        elif self.setup.engine_path.text().strip():
            self.review_panel.set_details(played_text, "Analyzing…", "Analyzing…")
            self.review_timer.start()
        else:
            self.review_panel.set_details(played_text, "Engine unavailable", "—")

    def analyze_review_position(self) -> None:
        if self.review is None:
            return
        position = self.review.analysis_position(self.review.index)
        path = self.setup.engine_path.text().strip()
        if position is None or not path:
            return
        self.engine_failed = False
        self.runner.search(position, path, 2200, False)

    def show_review_analysis(self, analysis: PositionAnalysis) -> None:
        if self.review is None or analysis.best_move is None:
            return
        position = self.review.analysis_position(self.review.index)
        played = self.review.played_at(self.review.index)
        if position is None or played is None or position.fen() != analysis.fen:
            return
        candidate = analysis.candidates[0]
        score = candidate.score.white()
        mate = score.mate()
        evaluation = f"Mate {mate:+d}" if mate is not None else f"{(score.score() or 0) / 100:+.2f}"
        best_san = position.san(analysis.best_move)
        played_text = (
            f"{played[1].number}.{'..' if played[1].color == chess.BLACK else ''} "
            f"{played[1].san} ({'Black' if played[1].color == chess.BLACK else 'White'})"
        )
        self.review_panel.set_details(played_text, best_san, evaluation)
        best_move = analysis.best_move if self.preferences.show_best_move else None
        self.board.set_review_moves(played[0], best_move)
        self.evaluation_bar.set_score(candidate.score)
        self.engine_label.setText(
            "Blue: played move · Purple: engine best"
            if self.preferences.show_best_move
            else "Blue: played move"
        )

    def show_coach_move(self, analyzed: MoveAnalysis) -> None:
        if self.review is None:
            return
        played = self.review.played_at(analyzed.ply)
        position = self.review.analysis_position(analyzed.ply)
        if played is None or position is None:
            return
        best = chess.Move.from_uci(analyzed.best_uci)
        score = analyzed.best_score
        evaluation = (
            f"Mate {score.mate:+d}"
            if score.mate is not None
            else f"{(score.centipawns or 0) / 100:+.2f}"
        )
        played_text = (
            f"{played[1].number}.{'..' if played[1].color == chess.BLACK else ''} "
            f"{played[1].san} ({'Black' if played[1].color == chess.BLACK else 'White'})"
        )
        self.review_panel.set_details(played_text, analyzed.best_san, evaluation)
        self.board.set_review_moves(played[0], best if self.preferences.show_best_move else None)
        badge, color = BADGES[analyzed.classification]
        self.board.set_classification(f"{analyzed.classification.value.title()} {badge}", color)
        self.evaluation_bar.set_score(pov_score(score))
        self.engine_label.setText(
            f"{analyzed.classification.value.title()} · {analyzed.accuracy:.1f}% move accuracy"
        )

    def start_coach_analysis(self) -> None:
        if self.review is None:
            return
        path = self.setup.engine_path.text().strip()
        if not path:
            self.statusBar().showMessage("Select a Stockfish executable before analysis.")
            return
        self.runner.cancel()
        self.review_timer.stop()
        self.coach_running = True
        self.coach_panel.set_running(True)
        settings = self.coach_settings if self.coach_panel.use_cloud else Settings()
        self.coach_runner.start(
            self.review.data,
            path,
            self.coach_repository,
            settings,
            self.preferences.engine_profile(),
        )

    def coach_progress(self, progress: AnalysisProgress) -> None:
        self.coach_panel.set_progress(progress.completed, progress.total, progress.stage)

    def coach_result(self, bundle: CoachBundle) -> None:
        if self.review is None or bundle.analysis.game_id != self.review.data.id:
            return
        self.coach_running = False
        self.coach_bundle = bundle
        self.coach_panel.set_bundle(bundle, self.review.data.player_color, self.review.data.result)
        self.review_panel.set_analysis(bundle.analysis, self.review.data.player_color)
        self.history.set_classifications(bundle.analysis.moves)
        self.set_review_index(0)
        self.statusBar().showMessage("Full-game coaching analysis complete.")

    def coach_error(self, message: str) -> None:
        self.last_error = message
        self.coach_running = False
        self.coach_panel.set_running(False)
        self.coach_panel.set_resumable(
            self.coach_panel.progress.value(), self.coach_panel.progress.maximum(), "failed"
        )
        self.coach_panel.feedback.setText(
            f"{message}\nChoose Resume Analysis to reuse completed positions."
        )

    def cancel_coach_analysis(self) -> None:
        self.coach_runner.cancel()
        self.coach_running = False
        self.coach_panel.set_running(False)
        self.coach_panel.set_resumable(
            self.coach_panel.progress.value(), self.coach_panel.progress.maximum(), "cancelled"
        )

    def toggle_best_line(self) -> None:
        """Play or hide the stored engine continuation for the selected move."""
        if self.line_timer.isActive() or self.line_games:
            self.stop_best_line(restore=True)
            return
        if self.review is None or self.coach_bundle is None or self.review.index == 0:
            self.statusBar().showMessage("Choose an analyzed move to show its best line.")
            return
        analyzed = self.coach_bundle.analysis.moves[self.review.index - 1]
        board = chess.Board(analyzed.fen)
        game = Game(analyzed.fen)
        games = [game.copy()]
        for uci in analyzed.best_pv:
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves or not game.attempt_move(move):
                break
            board.push(move)
            games.append(game.copy())
        if len(games) < 2:
            self.statusBar().showMessage("No stored best line is available for this move.")
            return
        self.line_games = games
        self.line_step = 0
        self.review_panel.show_line_button.setText("Hide Best Line")
        self.advance_best_line()
        self.line_timer.start()

    def advance_best_line(self) -> None:
        """Advance one cached position without calling Stockfish again."""
        if self.line_step >= len(self.line_games):
            self.line_timer.stop()
            return
        self.game = self.line_games[self.line_step]
        self.board.game = self.game
        self.board.set_review_moves(None, None)
        self.board.set_classification("Best line", "#7b2f8e")
        self.board.input_allowed = False
        self.board.refresh()
        self.line_step += 1

    def stop_best_line(self, *, restore: bool = False) -> None:
        """Stop variation playback and optionally restore the selected game ply."""
        was_showing = bool(self.line_games)
        self.line_timer.stop()
        self.line_games = []
        self.line_step = 0
        self.review_panel.show_line_button.setText("Show Best Line")
        if restore and was_showing and self.review is not None:
            index = self.review.index
            self.game = self.review.game_at(index)
            self.board.game = self.game
            self.set_review_index(index)

    def toggle_retry_move(self) -> None:
        """Enter or leave an interactive attempt from the pre-move position."""
        if self.retry_ply is not None:
            self.finish_retry()
            return
        if self.review is None or self.coach_bundle is None or self.review.index == 0:
            self.statusBar().showMessage("Choose an analyzed move before retrying it.")
            return
        analyzed = self.coach_bundle.analysis.moves[self.review.index - 1]
        self.stop_best_line()
        self.retry_ply = analyzed.ply
        self.retry_hint_level = 0
        self.game = Game(analyzed.fen)
        self.board.game = self.game
        self.active = True
        self.board.set_review_moves(None, None)
        self.board.set_classification("Retry", "#356f8f")
        self.review_panel.set_retry_mode(True)
        self.coach_panel.feedback.setText(
            "Your turn: find a stronger move. The best move is hidden."
        )
        self.refresh()

    def handle_retry_attempt(self) -> None:
        """Check a legal retry against stored engine-verified candidates."""
        if self.retry_ply is None or self.coach_bundle is None:
            return
        analyzed = self.coach_bundle.analysis.moves[self.retry_ply - 1]
        attempted = self.game.position.move_stack[-1].uci()
        accepted = attempted in ((analyzed.best_uci,) + analyzed.alternative_moves)
        if accepted:
            self.board.input_allowed = False
            self.board.set_classification("Correct", "#4d8f55")
            self.coach_panel.feedback.setText(
                f"Correct. {analyzed.best_san} keeps the stronger continuation. "
                "Choose Return to Review when ready."
            )
            self.board.refresh()
            return
        self.game = Game(analyzed.fen)
        self.board.game = self.game
        self.board.clear_selection()
        self.coach_panel.feedback.setText(
            "That move is legal, but it misses the engine's main idea. "
            "Look for checks, captures, and direct threats, or ask for a hint."
        )
        self.refresh()

    def show_retry_hint(self) -> None:
        """Reveal the retry objective, candidate, then stored legal line."""
        if self.retry_ply is None or self.coach_bundle is None:
            return
        analyzed = self.coach_bundle.analysis.moves[self.retry_ply - 1]
        self.retry_hint_level = min(3, self.retry_hint_level + 1)
        theme = analyzed.tags[0].replace("_", " ") if analyzed.tags else "candidate moves"
        hints = (
            f"Focus on: {theme}.",
            f"Candidate move: {analyzed.best_san}.",
            f"Engine line: {san_variation(analyzed.fen, analyzed.best_pv)}",
        )
        self.coach_panel.feedback.setText(hints[self.retry_hint_level - 1])

    def finish_retry(self) -> None:
        """Return from retry to the exact reviewed move."""
        if self.retry_ply is None or self.review is None:
            return
        ply = self.retry_ply
        self.retry_ply = None
        self.retry_hint_level = 0
        self.active = False
        self.review_panel.set_retry_mode(False)
        self.game = self.review.game_at(ply)
        self.board.game = self.game
        self.set_review_index(ply)

    def open_practice(self) -> None:
        self._show_destination(
            "practice",
            lambda: PracticeQueueDialog(self.coach_repository, self, self.course_catalog),
        )

    def open_lessons(self) -> None:
        lessons = self.coach_repository.lessons()
        if not lessons:
            self.statusBar().showMessage("No lessons yet. Analyze a game to create them.")
            return
        self._show_destination(
            "lessons", lambda: LessonsDialog(lessons, self.coach_repository, self)
        )

    def open_courses(self) -> None:
        self._show_destination(
            "courses", lambda: CourseLibraryDialog(self.course_catalog, self.coach_repository, self)
        )

    def open_learning_home(self) -> None:
        self._show_destination("learn", self._make_learning_home)

    def _make_learning_home(self) -> LearningHomeDialog:
        dialog = LearningHomeDialog(self.coach_repository, self.course_catalog, self.database, self)
        dialog.action_requested.connect(self._learning_action)
        return dialog

    def _show_destination(self, key: str, factory: Callable[[], QDialog]) -> None:
        existing = self.destination_dialogs.get(key)
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            return
        dialog = factory()
        self.destination_dialogs[key] = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _learning_action(self, action: str) -> None:
        if action == "practice":
            self.open_practice()
        elif action == "courses":
            self.open_courses()
        elif action.startswith("course:"):
            course_id = action.removeprefix("course:")
            course = next(
                (value for value in self.course_catalog.courses if value.id == course_id), None
            )
            if course is not None:
                self._show_destination(
                    f"course:{course_id}",
                    lambda: CourseDetailDialog(course, self.coach_repository, self),
                )
        elif action == "weaknesses":
            self.open_weaknesses()
        elif action == "latest":
            games = self.database.list_games()
            if games:
                data = self.database.load_game(games[0].id)
                if data is not None:
                    self.open_review(data)

    def open_weaknesses(self) -> None:
        self._show_destination("weaknesses", self._make_weaknesses)

    def _make_weaknesses(self) -> WeaknessDashboardDialog:
        dialog = WeaknessDashboardDialog(self.coach_repository, self)
        dialog.example_requested.connect(self.open_game_example)
        return dialog

    def open_game_example(self, game_id: str, ply: int) -> None:
        try:
            data = self.database.load_game(game_id)
        except (OSError, sqlite3.Error, ValueError) as error:
            self.statusBar().showMessage(f"Open example failed: {error}")
            return
        if data is None:
            self.statusBar().showMessage("The source game is no longer available.")
            return
        self.open_review(data)
        self.set_review_index(min(ply, len(data.moves)))

    def new_game(self) -> None:
        if not self.save_match():
            return
        self.runner.cancel()
        self.cancel_pending_bot()
        self.match = None
        self.active = False
        self.review_details = ""
        self.review = None
        self.review_cache.clear()
        self.coach_bundle = None
        self.coach_running = False
        self.coach_runner.cancel()
        self.review_timer.stop()
        self.line_timer.stop()
        self.retry_ply = None
        self.review_panel.hide()
        self.coach_panel.clear()
        self.coach_panel.hide()
        self.board.set_review_moves(None, None)
        self.evaluation_bar.clear()
        self.setup.setEnabled(True)
        self.setup.show()
        self.setup.update_mode()
        self.engine_label.clear()
        self.game.reset()
        self.board.clear_selection()
        self.statusBar().clearMessage()
        self.refresh()

    def undo(self) -> None:
        if self.match is not None and self.game.status().game_over:
            return
        self.runner.cancel()
        self.cancel_pending_bot()
        self.game.undo()
        if self.match is not None:
            while self.game.turn != self.match.player_color and self.game.can_undo:
                self.game.undo()
        self.board.clear_selection()
        self.statusBar().clearMessage()
        self.position_changed()

    def claim_draw(self) -> None:
        if self.match is not None and self.game.turn != self.match.player_color:
            return
        if self.game.claim_draw():
            self.board.clear_selection()
            self.statusBar().clearMessage()
            self.position_changed()

    def copy_pgn(self) -> None:
        QApplication.clipboard().setText(export_pgn(self.game))
        self.statusBar().showMessage("PGN copied to clipboard.", 4000)

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.save_match():
            event.ignore()
            return
        for dialog in tuple(self.destination_dialogs.values()):
            dialog.close()
        self.destination_dialogs.clear()
        self.cancel_pending_bot()
        self.runner.shutdown()
        self.coach_runner.shutdown()
        event.accept()
