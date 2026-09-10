import chess
import chess.engine
from PySide6.QtWidgets import QApplication

from chesscoach.engine.analysis import CandidateLine, PositionAnalysis
from chesscoach.engine.worker import EngineRunner, SearchResult
from chesscoach.ui.sandbox import AnalysisSandboxDialog


class FakeSandboxRunner(EngineRunner):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[chess.Board] = []

    def search(self, position: chess.Board, path: str, elo: int, play: bool) -> None:
        self.requests.append(position.copy())
        move = next(iter(position.legal_moves))
        line = CandidateLine(
            chess.engine.PovScore(chess.engine.Cp(35), chess.WHITE), (move,), 12
        )
        self.result.emit(SearchResult(PositionAnalysis(position.fen(), (line,)), None, elo))


def test_sandbox_loads_fen_and_updates_position(app: QApplication):
    dialog = AnalysisSandboxDialog()
    assert dialog.board.accessibleName() == "Self-analysis chess board"
    dialog.fen.setText("not a fen")
    dialog.load_position()
    assert dialog.status.text().startswith("Invalid position:")
    dialog.fen.setText("8/8/8/8/8/8/4K3/7k w - - 0 1")
    dialog.load_position()
    assert dialog.game.fen.startswith("8/8/8/8/8/8/4K3/7k")
    dialog.copy_position()
    assert QApplication.clipboard().text() == dialog.game.fen
    dialog.close()


def test_sandbox_engine_analysis_is_concise_and_position_scoped(app: QApplication) -> None:
    runner = FakeSandboxRunner()
    dialog = AnalysisSandboxDialog(runner=runner)
    dialog.engine_path.setText("fake-stockfish")
    dialog.analyze_position()
    assert runner.requests
    assert dialog.status.text() == "Analysis ready."
    assert "Best line:" in dialog.analysis.text()
    assert "Evaluation:" in dialog.analysis.text()

    dialog.fen.setText("8/8/8/8/8/8/4K3/7k w - - 0 1")
    dialog.load_position()
    assert dialog.analyze_button.isEnabled()
    dialog.analyze_position()
    assert "terminal" in dialog.status.text().lower()
    dialog.close()


def test_sandbox_ignores_stale_engine_result(app: QApplication) -> None:
    runner = FakeSandboxRunner()
    dialog = AnalysisSandboxDialog(runner=runner)
    dialog.engine_path.setText("fake-stockfish")
    dialog._analysis_fen = "old-position"
    stale = PositionAnalysis(
        "8/8/8/8/8/8/4K3/7k w - - 0 1",
        (),
    )
    dialog.analysis_result(SearchResult(stale, None, 1200))
    assert dialog.analysis.text() == "No engine analysis yet."
    assert dialog._analysis_fen == "old-position"
    dialog.close()
