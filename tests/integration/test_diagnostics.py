from PySide6.QtWidgets import QApplication

from chesscoach.ui.diagnostics import DiagnosticInfo, DiagnosticsDialog


def test_diagnostics_are_copyable_and_secret_free(app: QApplication) -> None:
    secret = "sk-private"
    info = DiagnosticInfo(
        "0.1.0",
        "C:/games/games.sqlite3",
        "C:/stockfish.exe",
        "Stockfish 17",
        True,
        f"Authentication failed for {secret}",
    )
    dialog = DiagnosticsDialog(info, secret=secret)
    assert secret not in dialog.text.text()
    assert "Stockfish 17" in dialog.text.text()
    assert "Analysis state:" in dialog.text.text()
    dialog.copy()
    assert app.clipboard().text() == dialog.text.text()
