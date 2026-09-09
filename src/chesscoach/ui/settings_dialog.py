"""Local engine and optional OpenAI configuration."""

from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chesscoach.ai.client import test_connection
from chesscoach.config import Settings, apply_process_settings, save_local_settings


class ConnectionWorker(QThread):
    completed = Signal(bool, str)

    def __init__(self, settings: Settings, parent: QDialog | None = None) -> None:
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:
        try:
            test_connection(self.settings)
        except Exception as error:
            self.completed.emit(False, _safe_connection_error(error))
        else:
            self.completed.emit(True, "Ready")


class SettingsDialog(QDialog):
    settings_saved = Signal(object)

    def __init__(
        self,
        settings: Settings,
        env_path: Path = Path(".env"),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.env_path = env_path
        self.worker: ConnectionWorker | None = None
        self.setWindowTitle("Chess Coach Settings")
        layout = QVBoxLayout(self)
        note = QLabel(
            "Stockfish powers chess analysis. OpenAI is optional and improves the wording "
            "of explanations. Credentials stay in the local ignored .env file."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.engine_path = QLineEdit(settings.stockfish_path)
        engine_row = QHBoxLayout()
        engine_row.addWidget(self.engine_path, 1)
        self.browse_button = QPushButton("Browse…")
        engine_row.addWidget(self.browse_button)
        form.addRow("Stockfish program", engine_row)
        self.api_key = QLineEdit(settings.openai_api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Optional project API key")
        form.addRow("OpenAI API key", self.api_key)
        self.show_key = QCheckBox("Show key while editing")
        form.addRow("", self.show_key)
        self.model = QLineEdit(settings.openai_model)
        self.model.setPlaceholderText("Model ID available to your API project")
        form.addRow("OpenAI model", self.model)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.key_page_button = QPushButton("Open API key page")
        self.test_button = QPushButton("Test OpenAI")
        actions.addWidget(self.key_page_button)
        actions.addWidget(self.test_button)
        layout.addLayout(actions)
        self.status = QLabel(self._readiness_text())
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        estimate = QLabel(
            "Cloud coaching is opt-in per review. It sends selected critical positions, "
            "usually a few short requests per game; API usage is billed by OpenAI."
        )
        estimate.setWordWrap(True)
        layout.addWidget(estimate)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(buttons)
        self.browse_button.clicked.connect(self._browse)
        self.show_key.toggled.connect(self._show_key)
        self.key_page_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://platform.openai.com/api-keys"))
        )
        self.test_button.clicked.connect(self._test)
        self.api_key.textChanged.connect(lambda: self.status.setText(self._readiness_text()))
        self.model.textChanged.connect(lambda: self.status.setText(self._readiness_text()))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        self.resize(560, 360)

    def current_settings(self) -> Settings:
        return Settings(
            openai_api_key=self.api_key.text().strip(),
            openai_model=self.model.text().strip(),
            stockfish_path=self.engine_path.text().strip(),
        )

    def _readiness_text(self) -> str:
        settings = self.current_settings()
        if not settings.openai_api_key and not settings.openai_model:
            return "OpenAI: Not configured — local coaching remains available."
        if not settings.openai_api_key or not settings.openai_model:
            return "OpenAI: Incomplete — enter both an API key and model."
        return "OpenAI: Configured — use Test OpenAI to verify access."

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish executable")
        if path:
            self.engine_path.setText(path)

    def _show_key(self, visible: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        self.api_key.setEchoMode(mode)

    def _test(self) -> None:
        settings = self.current_settings()
        try:
            settings.require_ai()
        except ValueError as error:
            self.status.setText(f"OpenAI: Not configured — {error}")
            return
        self.test_button.setEnabled(False)
        self.status.setText("OpenAI: Testing…")
        self.worker = ConnectionWorker(settings, self)
        self.worker.completed.connect(self._test_finished)
        self.worker.start()

    def _test_finished(self, success: bool, message: str) -> None:
        self.test_button.setEnabled(True)
        self.status.setText(
            f"OpenAI: {message}" if success else f"OpenAI: Connection failed — {message}"
        )
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    def _save(self) -> None:
        settings = self.current_settings()
        save_local_settings(
            self.env_path,
            {
                "OPENAI_API_KEY": settings.openai_api_key,
                "OPENAI_MODEL": settings.openai_model,
                "STOCKFISH_PATH": settings.stockfish_path,
            },
        )
        apply_process_settings(settings)
        self.settings_saved.emit(settings)
        self.accept()


def _safe_connection_error(error: Exception) -> str:
    """Return a short error without request bodies, headers, or credentials."""
    name = type(error).__name__
    text = str(error).splitlines()[0][:180]
    return f"{name}: {text}" if text else name
