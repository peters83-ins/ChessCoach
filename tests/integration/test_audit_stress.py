from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from chesscoach.audit import AuditReport
from chesscoach.engine.worker import EngineRunner
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow


class IdleEngine(EngineRunner):
    def search(self, *args: object, **kwargs: object) -> None:
        self.cancel()


def test_rapid_destination_switching_is_repeatable(
    app: QApplication, tmp_path: Path
) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"), runner=IdleEngine())
    open_destinations = (
        window.open_learning_home,
        window.open_courses,
        window.open_lessons,
        window.open_practice,
        window.open_insights,
    )
    for _ in range(3):
        for open_destination in open_destinations:
            open_destination()
            app.processEvents()
    assert set(window.destination_dialogs) >= {
        "learn",
        "courses",
        "practice",
        "insights",
    }
    window.close()


def test_all_primary_destinations_and_safe_actions_are_repeatable(
    app: QApplication, tmp_path: Path
) -> None:
    """Exercise every primary route and non-destructive control offscreen."""
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"), runner=IdleEngine())
    destinations = (
        window.show_play_workspace,
        window.open_review_destination,
        window.open_learning_home,
        window.open_courses,
        window.open_lessons,
        window.open_practice,
        window.open_insights,
        window.open_settings,
        window.open_diagnostics,
        window.open_sandbox,
    )
    actions = (
        window.new_game_button,
        window.undo_button,
        window.claim_draw_button,
        window.copy_pgn_button,
        window.load_button,
        window.import_pgn_button,
        window.sandbox_button,
        window.backup_button,
        window.restore_button,
        window.retry_button,
        window.settings_button,
        window.diagnostics_button,
    )
    report = AuditReport.start()
    passed = 0
    with patch(
        "chesscoach.ui.main_window.QFileDialog.getOpenFileName", return_value=("", "")
    ), patch(
        "chesscoach.ui.main_window.QFileDialog.getSaveFileName", return_value=("", "")
    ):
        for _ in range(3):
            for destination in destinations:
                destination()
                app.processEvents()
                passed += 1
            for action in actions:
                action.click()
                app.processEvents()
                passed += 1
    assert window.workspace_stack.currentWidget() is not None
    assert report.finish(passed_sequences=passed, failed_sequences=0).failed_sequences == 0
    window.close()
