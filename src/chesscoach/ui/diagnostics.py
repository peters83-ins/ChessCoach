"""Copyable, secret-free application diagnostics."""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QVBoxLayout, QWidget


@dataclass(frozen=True)
class DiagnosticInfo:
    app_version: str
    database_path: str
    engine_path: str
    engine_version: str
    ai_ready: bool
    last_error: str = ""

    def render(self, secret: str = "") -> str:
        error = self.last_error.replace(secret, "[redacted]") if secret else self.last_error
        return (
            f"Chess Coach {self.app_version}\n"
            f"Database: {self.database_path}\n"
            f"Stockfish path: {self.engine_path or 'Not configured'}\n"
            f"Stockfish version: {self.engine_version or 'Not detected yet'}\n"
            f"OpenAI: {'Ready' if self.ai_ready else 'Not configured; local coach active'}\n"
            f"Last error: {error or 'None'}"
        )


class DiagnosticsDialog(QDialog):
    def __init__(
        self,
        info: DiagnosticInfo,
        *,
        secret: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Diagnostics")
        layout = QVBoxLayout(self)
        self.text = QLabel(info.render(secret))
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.text)
        copy = QPushButton("Copy Diagnostics")
        close = QPushButton("Close")
        copy.clicked.connect(self.copy)
        close.clicked.connect(self.accept)
        layout.addWidget(copy)
        layout.addWidget(close)
        self.resize(600, 320)

    def copy(self) -> None:
        QApplication.clipboard().setText(self.text.text())
