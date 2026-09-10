from pathlib import Path

import chess
from PySide6.QtWidgets import QApplication

from chesscoach.engine.worker import EngineRunner
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow


class IdleEngine(EngineRunner):
    def search(self, *args: object, **kwargs: object) -> None:
        self.cancel()


def test_navigation_destinations_can_stay_open_and_switch(
    app: QApplication, tmp_path: Path
) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"), runner=IdleEngine())
    window.open_courses()
    first = window.destination_dialogs["courses"]
    assert window.workspace_stack.currentWidget() is first
    window.open_courses()
    assert window.destination_dialogs["courses"] is first
    window.open_learning_home()
    assert set(window.destination_dialogs) >= {"courses", "learn"}
    assert window.workspace_stack.currentWidget() is window.destination_dialogs["learn"]
    window.show_play_workspace()
    assert window.workspace_stack.currentIndex() == 0
    window.close()


def test_navigation_preserves_unsaved_match_state(app: QApplication, tmp_path: Path) -> None:
    window = MainWindow(database=GameDatabase(tmp_path / "games.sqlite3"), runner=IdleEngine())
    window.setup.mode.setCurrentIndex(1)
    window.start_match()
    window.board.select_square(chess.E2)
    window.board.select_square(chess.E4)
    assert [move.san for move in window.game.history()] == ["e4"]
    window.open_courses()
    window.show_play_workspace()
    assert window.navigator.current == "play"
    assert [move.san for move in window.game.history()] == ["e4"]
    window.close()
