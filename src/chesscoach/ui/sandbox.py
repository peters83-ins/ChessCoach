"""Self-analysis board for exploring positions and requesting local engine lines."""

import chess
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chesscoach.chess.game import Game
from chesscoach.engine.analysis import PositionAnalysis
from chesscoach.engine.worker import EngineRunner, SearchResult, WorkerState
from chesscoach.ui.chess_board import ChessBoard


class AnalysisSandboxDialog(QDialog):
    """Play through a position locally and optionally inspect a legal engine PV."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        engine_path: str = "",
        runner: EngineRunner | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Self-analysis sandbox")
        self.resize(700, 620)
        self.game = Game()
        self.runner = runner or EngineRunner(self)
        self._analysis_fen = ""
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("FEN"))
        self.fen = QLineEdit(self.game.fen)
        self.fen.setAccessibleName("Sandbox position FEN")
        controls.addWidget(self.fen, 1)
        self.load_button = QPushButton("Load position")
        self.load_button.setAccessibleName("Load sandbox FEN")
        controls.addWidget(self.load_button)
        layout.addLayout(controls)
        engine_controls = QHBoxLayout()
        engine_controls.addWidget(QLabel("Stockfish"))
        self.engine_path = QLineEdit(engine_path)
        self.engine_path.setPlaceholderText("Path to Stockfish executable (optional)")
        self.engine_path.setAccessibleName("Sandbox Stockfish executable")
        engine_controls.addWidget(self.engine_path, 1)
        engine_controls.addWidget(QLabel("ELO"))
        self.elo = QSpinBox()
        self.elo.setRange(800, 2400)
        self.elo.setSingleStep(100)
        self.elo.setValue(1200)
        self.elo.setAccessibleName("Sandbox engine strength")
        engine_controls.addWidget(self.elo)
        self.analyze_button = QPushButton("Analyze position")
        self.analyze_button.setAccessibleName("Analyze sandbox position")
        engine_controls.addWidget(self.analyze_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setAccessibleName("Cancel sandbox analysis")
        self.cancel_button.setEnabled(False)
        engine_controls.addWidget(self.cancel_button)
        layout.addLayout(engine_controls)
        self.board = ChessBoard(self.game)
        self.board.setAccessibleName("Self-analysis chess board")
        layout.addWidget(self.board, 1)
        self.status = QLabel("Explore this position locally, or analyze it with Stockfish.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.analysis = QLabel("No engine analysis yet.")
        self.analysis.setWordWrap(True)
        self.analysis.setAccessibleName("Sandbox engine analysis")
        layout.addWidget(self.analysis)
        self.copy_fen = QPushButton("Copy current FEN")
        self.copy_fen.setAccessibleName("Copy sandbox FEN")
        layout.addWidget(self.copy_fen)
        self.load_button.clicked.connect(self.load_position)
        self.board.game_changed.connect(self.position_changed)
        self.copy_fen.clicked.connect(self.copy_position)
        self.analyze_button.clicked.connect(self.analyze_position)
        self.cancel_button.clicked.connect(self.cancel_analysis)
        self.engine_path.textChanged.connect(self._update_analysis_controls)
        self.runner.result.connect(self.analysis_result)
        self.runner.error.connect(self.analysis_error)
        self._update_analysis_controls()

    def load_position(self) -> None:
        self.cancel_analysis()
        try:
            self.game = Game(self.fen.text().strip())
        except ValueError as error:
            self.status.setText(f"Invalid position: {error}")
            return
        self.board.game = self.game
        self.board.clear_selection()
        self.analysis.setText("No engine analysis yet.")
        self.status.setText("Position loaded. Select a piece, then a legal destination.")
        self._update_analysis_controls()

    def position_changed(self) -> None:
        self.cancel_analysis()
        self.fen.setText(self.game.fen)
        self.status.setText(self.game.status().message)
        self.analysis.setText("Position changed. Analyze again for a fresh line.")
        self._update_analysis_controls()

    def _update_analysis_controls(self) -> None:
        self.analyze_button.setEnabled(
            bool(self.engine_path.text().strip()) and not self.game.status().game_over
        )

    def analyze_position(self) -> None:
        if self.game.status().game_over:
            self.status.setText("This position is terminal; there is no move to analyze.")
            return
        path = self.engine_path.text().strip()
        if not path:
            self.status.setText("Select a Stockfish executable before analyzing.")
            return
        self._analysis_fen = self.game.fen
        self.analyze_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status.setText("Stockfish is analyzing…")
        self.analysis.setText("Loading engine analysis…")
        self.runner.search(self.game.position, path, self.elo.value(), False)

    def cancel_analysis(self) -> None:
        if self.runner.state in {WorkerState.SEARCHING, WorkerState.READY}:
            self.runner.cancel()
        self._analysis_fen = ""
        self.cancel_button.setEnabled(False)
        self._update_analysis_controls()

    def analysis_result(self, result: SearchResult) -> None:
        if not self._analysis_fen or result.analysis.fen != self.game.fen:
            return
        self._analysis_fen = ""
        self.cancel_button.setEnabled(False)
        self._update_analysis_controls()
        self.status.setText("Analysis ready.")
        self.analysis.setText(format_position_analysis(result.analysis))

    def analysis_error(self, message: str) -> None:
        if not self._analysis_fen:
            return
        self._analysis_fen = ""
        self.cancel_button.setEnabled(False)
        self._update_analysis_controls()
        self.status.setText(message)
        self.analysis.setText("No engine analysis available. Check the path and retry.")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.cancel_analysis()
        self.runner.shutdown()
        super().closeEvent(event)

    def copy_position(self) -> None:
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(self.game.fen)
        self.status.setText("Current FEN copied.")


def format_position_analysis(analysis: PositionAnalysis) -> str:
    """Format verified engine output as concise SAN without trusting free text."""
    if not analysis.candidates:
        return "No legal engine line was returned."
    board = chess.Board(analysis.fen)
    candidate = analysis.candidates[0]
    san_moves: list[str] = []
    for move in candidate.moves:
        if move not in board.legal_moves:
            return "Engine returned an invalid principal variation."
        san_moves.append(board.san(move))
        board.push(move)
    score = candidate.score.white()
    return f"Best line: {' '.join(san_moves) or 'No move'} · Evaluation: {score} · Depth: {candidate.depth}"
