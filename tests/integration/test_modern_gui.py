from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow
from chesscoach.ui.theme import MODERN_STYLESHEET


def test_modern_theme_is_applied_to_primary_actions(app: QApplication, tmp_path: Path) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"))
    assert MODERN_STYLESHEET in window.styleSheet()
    assert window.new_game_button.objectName() == "primaryAction"
    assert window.save_button.objectName() == "primaryAction"
    assert window.setup.start_button.objectName() == "primaryAction"
    assert not window.tools_group.isChecked()
    assert not window.load_button.isVisible()
    assert window.play_action.isCheckable()
    assert window.play_action.isChecked()
    assert "QScrollBar::handle:vertical" in MODERN_STYLESHEET
    assert "font-family" in MODERN_STYLESHEET
    window.close()


def test_play_controls_have_predictable_keyboard_order_and_disabled_help(
    app: QApplication, tmp_path: Path
) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"))
    focus_chain = []
    current = window.setup.mode
    for _ in range(20):
        focus_chain.append(current)
        current = current.nextInFocusChain()
        if current is window.setup.start_button:
            focus_chain.append(current)
            break
    assert focus_chain.index(window.setup.mode) < focus_chain.index(window.setup.color)
    assert focus_chain.index(window.setup.color) < focus_chain.index(window.setup.difficulty)
    assert focus_chain.index(window.setup.difficulty) < focus_chain.index(window.setup.start_button)
    assert window.undo_button.toolTip() == "Undo is available during an active game."
    assert window.save_button.toolTip() == "Make at least one move before saving the match."
    window.close()
