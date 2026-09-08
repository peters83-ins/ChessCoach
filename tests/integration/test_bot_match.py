import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import chess
import chess.engine
import pytest
from PySide6.QtWidgets import QApplication

from chesscoach.chess.pgn import parse_pgn
from chesscoach.engine.analysis import CandidateLine, PositionAnalysis
from chesscoach.engine.worker import EngineRunner, SearchResult
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.main_window import MainWindow


class FakeRunner(EngineRunner):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[tuple[chess.Board, str, int, bool]] = []

    def search(self, position: chess.Board, path: str, elo: int, play: bool) -> None:
        self.cancel()
        self.requests.append((position, path, elo, play))

    def respond(self, move: str | None = None) -> None:
        position = self.requests[-1][0]
        best = next(iter(position.legal_moves))
        analysis = PositionAnalysis(
            position.fen(),
            (CandidateLine(chess.engine.PovScore(chess.engine.Cp(25), chess.WHITE), (best,), 10),),
        )
        self.result.emit(SearchResult(analysis, chess.Move.from_uci(move) if move else None, 1500))


@pytest.fixture
def bot(app: QApplication, tmp_path: Path) -> Iterator[tuple[MainWindow, FakeRunner]]:
    runner = FakeRunner()
    window = MainWindow(database=GameDatabase(tmp_path / "matches.sqlite3"), runner=runner)
    window.setup.engine_path.setText("test-stockfish")
    window.show()
    yield window, runner
    window.close()
    window.deleteLater()
    app.processEvents()


def human_move(window: MainWindow, source: str, target: str) -> None:
    window.board.select_square(chess.parse_square(source))
    window.board.select_square(chess.parse_square(target))


def test_setup_white_turns_and_undo(bot: tuple[MainWindow, FakeRunner]) -> None:
    window, runner = bot
    human_move(window, "e2", "e4")
    assert not window.game.history()
    window.setup.start_button.click()
    assert runner.requests[-1][3] is False
    runner.respond()
    assert "White eval: +0.25" in window.engine_label.text()
    assert window.match.elo == 1500
    human_move(window, "e2", "e4")
    assert runner.requests[-1][3] is True
    human_move(window, "e7", "e5")
    assert len(window.game.history()) == 1  # Human cannot play the bot's turn.
    runner.respond("e7e5")
    assert len(window.game.history()) == 2
    assert runner.requests[-1][3] is False
    assert len(window.match.move_timestamps) == 2
    window.undo_button.click()
    assert window.game.fen == chess.STARTING_FEN
    assert window.match.move_timestamps == []


def test_black_gets_engine_opening(bot: tuple[MainWindow, FakeRunner]) -> None:
    window, runner = bot
    window.setup.color.setCurrentIndex(1)
    window.start_match()
    assert window.board.orientation == chess.BLACK
    assert not window.board.input_allowed
    assert runner.requests[-1][3]
    runner.respond("e2e4")
    assert window.board.input_allowed
    assert not window.undo_button.isEnabled()
    human_move(window, "e7", "e5")
    assert len(window.game.history()) == 2


def test_late_result_after_new_game_rejected(bot: tuple[MainWindow, FakeRunner]) -> None:
    window, runner = bot
    window.start_match()
    human_move(window, "e2", "e4")
    old_generation = runner.generation
    window.new_game()
    runner.respond("e7e5")
    assert window.game.fen == chess.STARTING_FEN
    assert not window.active
    # Also exercise the runner guard when a replacement match has the same FEN.
    delivered = []
    runner.result.connect(delivered.append)
    runner._result(old_generation, object())
    assert delivered == []


def test_error_retry_and_illegal_engine_move(bot: tuple[MainWindow, FakeRunner]) -> None:
    window, runner = bot
    window.start_match()
    runner.error.emit("Missing executable")
    assert window.retry_button.isEnabled()
    window.retry_button.click()
    assert not window.retry_button.isEnabled()
    human_move(window, "e2", "e4")
    runner.respond("e7e4")
    assert len(window.game.history()) == 1
    assert window.retry_button.isEnabled()


def test_completed_game_autosave_and_manual_retry(bot: tuple[MainWindow, FakeRunner]) -> None:
    window, runner = bot
    window.start_match()
    human_move(window, "f2", "f3")
    runner.respond("e7e5")
    human_move(window, "g2", "g4")
    runner.respond("d8h4")
    assert window.game.status().game_over
    assert "Match saved" in window.statusBar().currentMessage()
    assert not window.undo_button.isEnabled()
    window.save_button.click()
    with sqlite3.connect(window.database.path) as connection:
        rows = connection.execute("SELECT data_json FROM games").fetchall()
    assert len(rows) == 1
    data = json.loads(rows[0][0])
    assert data["ended_at"] is not None
    assert data["bot_elo"] == 1500
    assert len(data["move_timestamps"]) == 4
    assert parse_pgn(data["pgn"]).fen == window.game.fen


def test_save_failure_preserves_game(bot: tuple[MainWindow, FakeRunner], tmp_path: Path) -> None:
    window, runner = bot
    window.start_match()
    human_move(window, "e2", "e4")
    original = window.database
    window.database = GameDatabase(tmp_path)  # Opening a directory as SQLite must fail.
    before = window.game.fen
    window.new_game()
    assert window.game.fen == before
    assert "Could not save" in window.statusBar().currentMessage()
    assert not window.close()
    window.database = original
    assert window.save_match()


def test_missing_engine_and_local_mode(bot: tuple[MainWindow, FakeRunner]) -> None:
    window, runner = bot
    window.setup.engine_path.clear()
    window.start_match()
    assert not window.active
    assert not runner.requests
    window.setup.mode.setCurrentIndex(1)
    window.start_match()
    human_move(window, "e2", "e4")
    human_move(window, "e7", "e5")
    assert len(window.game.history()) == 2
    assert window.match is None
