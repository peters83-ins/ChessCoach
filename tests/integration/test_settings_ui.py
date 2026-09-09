from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog

from chesscoach.config import Settings
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.diagnostics import DiagnosticsDialog
from chesscoach.ui.first_run import FirstRunWizard
from chesscoach.ui.main_window import MainWindow
from chesscoach.ui.settings_dialog import SettingsDialog


def test_settings_dialog_masks_and_saves_key(app: QApplication, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    dialog = SettingsDialog(Settings(), env_file)
    dialog.api_key.setText("secret")
    dialog.model.setText("model")
    assert not dialog.show_key.isChecked()
    dialog._save()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert "OPENAI_API_KEY=secret" in env_file.read_text()


def test_settings_connection_states(app: QApplication) -> None:
    dialog = SettingsDialog(Settings())
    assert "Not configured" in dialog.status.text()
    dialog.api_key.setText("key")
    dialog.model.setText("model")
    with patch("chesscoach.ui.settings_dialog.ConnectionWorker.start"):
        dialog._test()
    assert dialog.status.text() == "OpenAI: Testing…"
    dialog._test_finished(False, "AuthenticationError")
    assert "Connection failed" in dialog.status.text()


def test_first_run_wizard_saves_playable_setup(app: QApplication, tmp_path: Path) -> None:
    engine = tmp_path / "stockfish.exe"
    engine.write_text("engine")
    env_file = tmp_path / ".env"
    preferences = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    wizard = FirstRunWizard(
        Settings(),
        tmp_path / "games" / "games.sqlite3",
        env_file,
        preferences,
    )
    wizard.engine_path.setText(str(engine))
    wizard._refresh_ready_page(wizard.pageIds()[-1])
    assert "Stockfish: Ready" in wizard.checks_label.text()
    wizard.accept()
    assert f"STOCKFISH_PATH={engine}" in env_file.read_text()
    assert preferences.value("setup/complete", False, bool)


def test_main_window_settings_and_diagnostics_buttons(app: QApplication, tmp_path: Path) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"))
    window.show()
    with (
        patch.object(SettingsDialog, "exec", return_value=QDialog.DialogCode.Rejected) as settings,
        patch.object(DiagnosticsDialog, "exec", return_value=QDialog.DialogCode.Accepted) as diag,
    ):
        window.settings_button.click()
        window.diagnostics_button.click()
    settings.assert_called_once()
    diag.assert_called_once()
    window.close()
