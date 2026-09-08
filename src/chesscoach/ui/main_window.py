"""Match setup, human/engine turns, and explicit persistence feedback."""

import sqlite3
from pathlib import Path

import chess
from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chesscoach.chess.game import Game
from chesscoach.chess.pgn import export_pgn
from chesscoach.engine.worker import EngineRunner, SearchResult
from chesscoach.storage.database import GameDatabase
from chesscoach.storage.match import BotMatch
from chesscoach.ui.chess_board import ChessBoard
from chesscoach.ui.match_setup import MatchSetup
from chesscoach.ui.move_history import MoveHistory
from chesscoach.ui.saved_games import SavedGamesDialog


class MainWindow(QMainWindow):
    def __init__(
        self,
        game: Game | None = None,
        *,
        database: GameDatabase | None = None,
        runner: EngineRunner | None = None,
    ) -> None:
        super().__init__()
        self.game = game if game is not None else Game()
        self.active = game is not None
        self.match: BotMatch | None = None
        self.engine_path = ""
        self.engine_failed = False
        self.review_details = ""
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
        self.setWindowTitle("Chess Coach")
        self.resize(1050, 740)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        self.board = ChessBoard(self.game)
        layout.addWidget(self.board, 3)
        sidebar = QVBoxLayout()
        layout.addLayout(sidebar, 1)
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
        self.engine_label = QLabel("")
        self.engine_label.setWordWrap(True)
        sidebar.addWidget(self.engine_label)
        self.history = MoveHistory()
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
        for button in (
            self.new_game_button,
            self.undo_button,
            self.claim_draw_button,
            self.copy_pgn_button,
            self.save_button,
            self.load_button,
            self.retry_button,
        ):
            sidebar.addWidget(button)
        self.new_game_button.clicked.connect(self.new_game)
        self.undo_button.clicked.connect(self.undo)
        self.claim_draw_button.clicked.connect(self.claim_draw)
        self.copy_pgn_button.clicked.connect(self.copy_pgn)
        self.save_button.clicked.connect(self.save_match)
        self.load_button.clicked.connect(self.load_saved_game)
        self.retry_button.clicked.connect(self.request_engine)
        self.board.game_changed.connect(self.position_changed)
        self.board.message.connect(self.show_board_message)
        self.refresh()

    def show_board_message(self, message: str) -> None:
        self.statusBar().showMessage(message)
        if not self.active and not self.review_details:
            self.status_label.setText(message)

    def refresh(self) -> None:
        status = self.game.status()
        self.status_label.setText(
            self.review_details
            if self.review_details
            else status.message
            if self.active
            else "Choose color and difficulty, then Start Match."
        )
        self.history.set_moves(self.game.history())
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
            self.match is not None and self.engine_failed and not status.game_over
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
        self.game.reset()
        self.active = True
        self.engine_failed = False
        self.review_details = ""
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
        self.setup.setEnabled(False)
        self.statusBar().clearMessage()
        self.engine_label.clear()
        self.refresh()
        self.request_engine()

    def position_changed(self) -> None:
        if self.match is not None:
            self.match.record_position()
        self.refresh()
        if self.game.status().game_over:
            self.runner.cancel()
            self.engine_label.clear()
            self.save_match()
        else:
            self.request_engine()

    def request_engine(self) -> None:
        if self.match is None or not self.active or self.game.status().game_over:
            return
        self.engine_failed = False
        self.engine_label.setText("Stockfish is thinking…")
        self.runner.search(
            self.game.position,
            self.engine_path,
            self.match.elo,
            self.game.turn != self.match.player_color,
        )
        self.refresh()

    def engine_result(self, result: SearchResult) -> None:
        if self.match is None or not self.active or result.analysis.fen != self.game.fen:
            return
        self.match.elo = result.actual_elo
        if result.move is not None:
            if self.game.turn == self.match.player_color or not self.game.attempt_move(result.move):
                self.engine_error("Stockfish returned a move for the wrong position. Retry Engine.")
                return
            self.board.clear_selection()
            self.position_changed()
            return
        candidate = result.analysis.candidates[0]
        score = candidate.score.white()
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

    def engine_error(self, message: str) -> None:
        self.engine_failed = True
        self.engine_label.setText(message)
        self.refresh()

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
        dialog = SavedGamesDialog(games, str(self.database.path), self)
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
        game = Game(data.fens[0])
        for uci in data.moves:
            if not game.attempt_move(chess.Move.from_uci(uci)):
                self.statusBar().showMessage("Load failed: invalid move history.")
                return
        self.runner.cancel()
        self.game = game
        self.board.game = game
        self.match = None
        self.active = False
        self.review_details = (
            f"Saved game for analysis · Player {data.player_color.title()} · "
            f"Bot {data.bot_elo} · Result {data.result}"
        )
        self.setup.setEnabled(False)
        self.board.set_orientation(data.player_color == "white")
        self.engine_label.clear()
        self.statusBar().showMessage("Saved game loaded.")
        self.refresh()

    def new_game(self) -> None:
        if not self.save_match():
            return
        self.runner.cancel()
        self.match = None
        self.active = False
        self.review_details = ""
        self.setup.setEnabled(True)
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
        self.runner.shutdown()
        event.accept()
