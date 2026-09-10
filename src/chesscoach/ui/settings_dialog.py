"""Local engine and optional OpenAI configuration."""

from pathlib import Path

from PySide6.QtCore import QSettings, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from chesscoach.ai.client import test_connection
from chesscoach.config import Settings, apply_process_settings, save_local_settings
from chesscoach.distribution import current_version, runtime_paths
from chesscoach.preferences import UserPreferences
from chesscoach.storage.coach import CoachRepository
from chesscoach.update_checker import UpdateChecker, UpdateCheckError, UpdateCheckResult


class ConnectionWorker(QThread):
    completed = Signal(bool, str)

    def __init__(self, settings: Settings, parent: QDialog | None = None) -> None:
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:
        try:
            test_connection(self.settings)
        except Exception as error:
            self.completed.emit(False, _safe_connection_error(error, self.settings.openai_api_key))
        else:
            self.completed.emit(True, "Ready")


class UpdateWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, checker: UpdateChecker, parent: QDialog | None = None) -> None:
        super().__init__(parent)
        self.checker = checker

    def run(self) -> None:
        try:
            self.completed.emit(self.checker.check(force=True))
        except UpdateCheckError as error:
            self.failed.emit(str(error))


class SettingsDialog(QDialog):
    settings_saved = Signal(object)
    preferences_saved = Signal(object)

    def __init__(
        self,
        settings: Settings,
        env_path: Path = Path(".env"),
        preferences: UserPreferences | None = None,
        preference_settings: QSettings | None = None,
        repository: CoachRepository | None = None,
        update_manifest_url: str = (
            "https://github.com/peters83-ins/ChessCoach/releases/latest/download/manifest.json"
        ),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.env_path = env_path
        self.preferences = preferences or UserPreferences()
        self.preference_settings = preference_settings
        self.worker: ConnectionWorker | None = None
        self.update_worker: UpdateWorker | None = None
        self.update_manifest_url = update_manifest_url
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
        preference_form = QFormLayout()
        self.profile = QComboBox()
        profiles = repository.profiles() if repository is not None else ()
        if not profiles:
            self.profile.addItem("Local player", "default")
        else:
            for profile in profiles:
                self.profile.addItem(profile.name, profile.profile_id)
        self._select_data(self.profile, self.preferences.profile_id)
        preference_form.addRow("Learner profile", self.profile)
        self.orientation = QComboBox()
        self.orientation.addItem("Player side", "player")
        self.orientation.addItem("White", "white")
        self.orientation.addItem("Black", "black")
        self._select_data(self.orientation, self.preferences.board_orientation)
        preference_form.addRow("Review orientation", self.orientation)
        self.board_theme = QComboBox()
        self.board_theme.addItem("Classic", "classic")
        self.board_theme.addItem("High contrast", "high_contrast")
        self._select_data(self.board_theme, self.preferences.board_theme)
        preference_form.addRow("Board theme", self.board_theme)
        self.piece_scale = QSpinBox()
        self.piece_scale.setRange(75, 120)
        self.piece_scale.setSuffix("%")
        self.piece_scale.setValue(self.preferences.piece_scale)
        preference_form.addRow("Piece size", self.piece_scale)
        self.analysis_profile = QComboBox()
        self.analysis_profile.addItem("Quick", "quick")
        self.analysis_profile.addItem("Standard", "standard")
        self.analysis_profile.addItem("Deep", "deep")
        self._select_data(self.analysis_profile, self.preferences.analysis_profile)
        preference_form.addRow("Analysis depth", self.analysis_profile)
        self.review_perspective = QComboBox()
        self.review_perspective.addItem("My moves", "player")
        self.review_perspective.addItem("Both sides", "both")
        self.review_perspective.addItem("All moves", "all")
        self._select_data(self.review_perspective, self.preferences.review_perspective)
        preference_form.addRow("Coach perspective", self.review_perspective)
        self.show_best_move = QCheckBox("Highlight the engine move on the board")
        self.show_best_move.setChecked(self.preferences.show_best_move)
        preference_form.addRow("Best move", self.show_best_move)
        self.verbosity = QComboBox()
        self.verbosity.addItem("Concise", "concise")
        self.verbosity.addItem("Detailed", "detailed")
        self._select_data(self.verbosity, self.preferences.coach_verbosity)
        preference_form.addRow("Coach feedback", self.verbosity)
        self.text_scale = QSpinBox()
        self.text_scale.setRange(90, 140)
        self.text_scale.setSuffix("%")
        self.text_scale.setValue(self.preferences.text_scale)
        preference_form.addRow("Text size", self.text_scale)
        self.bot_delay = QComboBox()
        for label, value in (
            ("Instant", 0),
            ("Brief · 300 ms", 300),
            ("Normal · 600 ms", 600),
            ("Slow · 900 ms", 900),
        ):
            self.bot_delay.addItem(label, value)
        delay_index = self.bot_delay.findData(self.preferences.bot_move_delay_ms)
        self.bot_delay.setCurrentIndex(delay_index if delay_index >= 0 else 2)
        preference_form.addRow("Bot reply delay", self.bot_delay)
        layout.addLayout(preference_form)
        actions = QHBoxLayout()
        self.key_page_button = QPushButton("Open API key page")
        self.test_button = QPushButton("Test OpenAI")
        self.update_button = QPushButton("Check for Updates")
        actions.addWidget(self.key_page_button)
        actions.addWidget(self.test_button)
        actions.addWidget(self.update_button)
        layout.addLayout(actions)
        self.status = QLabel(self._readiness_text())
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.update_status = QLabel("Updates are checked only when requested.")
        self.update_status.setWordWrap(True)
        layout.addWidget(self.update_status)
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
        self.update_button.clicked.connect(self._check_updates)
        self.api_key.textChanged.connect(lambda: self.status.setText(self._readiness_text()))
        self.model.textChanged.connect(lambda: self.status.setText(self._readiness_text()))
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        self.resize(600, 650)

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def current_preferences(self) -> UserPreferences:
        return UserPreferences(
            profile_id=str(self.profile.currentData()),
            board_orientation=str(self.orientation.currentData()),
            board_theme=str(self.board_theme.currentData()),
            piece_scale=self.piece_scale.value(),
            analysis_profile=str(self.analysis_profile.currentData()),
            review_perspective=str(self.review_perspective.currentData()),
            show_best_move=self.show_best_move.isChecked(),
            coach_verbosity=str(self.verbosity.currentData()),
            text_scale=self.text_scale.value(),
            bot_move_delay_ms=int(self.bot_delay.currentData()),
        )

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

    def _check_updates(self) -> None:
        self.update_button.setEnabled(False)
        self.update_status.setText("Checking for updates…")
        checker = UpdateChecker(
            self.update_manifest_url,
            current_version(),
            runtime_paths().data_dir / "update-cache.json",
        )
        self.update_worker = UpdateWorker(checker, self)
        self.update_worker.completed.connect(self._updates_finished)
        self.update_worker.failed.connect(self._updates_failed)
        self.update_worker.start()

    def _updates_finished(self, result: UpdateCheckResult) -> None:
        self.update_button.setEnabled(True)
        if result.update is None:
            self.update_status.setText("Updates: You are up to date.")
            if self.update_worker is not None:
                self.update_worker.deleteLater()
                self.update_worker = None
            return
        update = result.update
        self.update_status.setText(f"Update available: Chess Coach {update.latest_version}.")
        self.update_button.setText("Open Release")
        self.update_button.clicked.disconnect(self._check_updates)
        self.update_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(update.installer_url))
        )
        if self.update_worker is not None:
            self.update_worker.deleteLater()
            self.update_worker = None

    def _updates_failed(self, message: str) -> None:
        self.update_button.setEnabled(True)
        self.update_status.setText(f"Updates: {message}.")
        if self.update_worker is not None:
            self.update_worker.deleteLater()
            self.update_worker = None

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
        preferences = self.current_preferences()
        if self.preference_settings is not None:
            preferences.save(self.preference_settings)
        self.settings_saved.emit(settings)
        self.preferences_saved.emit(preferences)
        self.accept()


def _safe_connection_error(error: Exception, secret: str = "") -> str:
    """Return a short error without request bodies, headers, or credentials."""
    name = type(error).__name__
    text = str(error).replace(secret, "[redacted]") if secret else str(error)
    text = text.splitlines()[0][:180]
    return f"{name}: {text}" if text else name
