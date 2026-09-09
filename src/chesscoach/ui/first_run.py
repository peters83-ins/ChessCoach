"""First-run guide for storage, Stockfish, and optional cloud coaching."""

from pathlib import Path

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from chesscoach.config import Settings, apply_process_settings, save_local_settings
from chesscoach.engine.discovery import discover_engine
from chesscoach.setup_checks import run_setup_checks


class FirstRunWizard(QWizard):
    settings_saved = Signal(object)

    def __init__(
        self,
        settings: Settings,
        database_path: Path,
        env_path: Path = Path(".env"),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database_path = database_path
        self.env_path = env_path
        self.setWindowTitle("Welcome to Chess Coach")
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.addPage(self._welcome_page())
        self.addPage(self._engine_page(settings.stockfish_path or discover_engine()))
        self.addPage(self._ai_page(settings))
        self.addPage(self._ready_page())
        self.currentIdChanged.connect(self._refresh_ready_page)
        self.resize(600, 430)

    def _welcome_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("Welcome")
        layout = QVBoxLayout(page)
        text = QLabel(
            "Chess Coach saves games locally and uses Stockfish for chess analysis. "
            "OpenAI is optional and only improves coaching explanations."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        return page

    def _engine_page(self, path: str) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("Choose Stockfish")
        layout = QVBoxLayout(page)
        help_text = QLabel(
            "Stockfish is the downloaded chess-engine program (stockfish.exe on Windows). "
            "Automatic detection is used when possible; otherwise browse to the extracted file."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        self.engine_path = QLineEdit(path)
        self.engine_path.setPlaceholderText("Path to stockfish.exe")
        layout.addWidget(self.engine_path)
        browse = QPushButton("Browse for Stockfish…")
        browse.clicked.connect(self._browse)
        layout.addWidget(browse)
        optional = QLabel(
            "You can finish setup without Stockfish, but games against the bot and "
            "analysis need it."
        )
        optional.setWordWrap(True)
        layout.addWidget(optional)
        return page

    def _ai_page(self, settings: Settings) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("Optional OpenAI coaching")
        layout = QFormLayout(page)
        info = QLabel(
            "Leave these blank for grounded local feedback. API usage is separate from a "
            "ChatGPT subscription and is only used when you opt in during review."
        )
        info.setWordWrap(True)
        layout.addRow(info)
        self.api_key = QLineEdit(settings.openai_api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.model = QLineEdit(settings.openai_model)
        self.model.setPlaceholderText("Model ID available to your API project")
        layout.addRow("API key", self.api_key)
        layout.addRow("Model", self.model)
        return page

    def _ready_page(self) -> QWizardPage:
        page = QWizardPage()
        page.setTitle("Setup check")
        layout = QVBoxLayout(page)
        self.checks_label = QLabel()
        self.checks_label.setWordWrap(True)
        layout.addWidget(self.checks_label)
        return page

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select Stockfish executable")
        if path:
            self.engine_path.setText(path)

    def _refresh_ready_page(self, page_id: int) -> None:
        if page_id != self.pageIds()[-1]:
            return
        checks = run_setup_checks(self.database_path, self.engine_path.text().strip())
        ai_ready = bool(self.api_key.text().strip() and self.model.text().strip())
        storage_mark = "✓" if checks.storage_ready else "✗"
        engine_mark = "✓" if checks.engine_ready else "○"
        engine_status = "Ready" if checks.engine_ready else "Not configured"
        ai_mark = "✓" if ai_ready else "○"
        ai_status = "Configured" if ai_ready else "Optional — local coach ready"
        self.checks_label.setText(
            f"✓ Application dependencies\n"
            f"{storage_mark} Saved-game folder: {self.database_path.parent}\n"
            f"{engine_mark} Stockfish: {engine_status}\n"
            f"{ai_mark} OpenAI: {ai_status}\n\n"
            "Choose Finish to open the playable match setup."
        )

    def accept(self) -> None:
        settings = Settings(
            openai_api_key=self.api_key.text().strip(),
            openai_model=self.model.text().strip(),
            stockfish_path=self.engine_path.text().strip(),
        )
        save_local_settings(
            self.env_path,
            {
                "OPENAI_API_KEY": settings.openai_api_key,
                "OPENAI_MODEL": settings.openai_model,
                "STOCKFISH_PATH": settings.stockfish_path,
            },
        )
        apply_process_settings(settings)
        QSettings().setValue("setup/complete", True)
        self.settings_saved.emit(settings)
        super().accept()
