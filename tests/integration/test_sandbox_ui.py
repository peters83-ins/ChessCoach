from PySide6.QtWidgets import QApplication

from chesscoach.ui.sandbox import AnalysisSandboxDialog


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
