from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import chess
import pytest
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from chesscoach.chess.pgn import parse_pgn
from chesscoach.coach.models import (
    AnalysisProfile,
    AnalysisProgress,
    EngineScore,
    Evidence,
    GameAnalysis,
    GamePhase,
    MoveAnalysis,
    MoveClassification,
    PhaseSummary,
)
from chesscoach.coach.pipeline import CoachPipeline
from chesscoach.engine.worker import EngineRunner
from chesscoach.preferences import UserPreferences
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameData, GameDatabase
from chesscoach.storage.match import BotMatch
from chesscoach.ui.coach_panel import LessonsDialog, PracticeDialog
from chesscoach.ui.learning_center import PracticeQueueDialog, WeaknessDashboardDialog
from chesscoach.ui.main_window import MainWindow
from chesscoach.ui.saved_games import SavedGamesDialog


class FakeEngineRunner(EngineRunner):
    def search(self, position, path, elo, play) -> None:
        self.cancel()


class FakeCoachRunner(QObject):
    progress = Signal(object)
    result = Signal(object)
    error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.requests = []
        self.cancelled = 0

    def start(self, *args) -> None:
        self.requests.append(args)

    def cancel(self) -> None:
        self.cancelled += 1

    def shutdown(self) -> None:
        self.cancel()


def data() -> GameData:
    return GameData.from_game(
        parse_pgn("1. f3 *"),
        match_id="coach-game",
        started_at="start",
        saved_at="saved",
        ended_at=None,
        player_color=chess.WHITE,
        bot_elo=1000,
        move_timestamps=("move",),
    )


def bundle():
    move = MoveAnalysis(
        1,
        chess.STARTING_FEN,
        "white",
        "f2f3",
        "f3",
        "e2e4",
        "e4",
        EngineScore(centipawns=50),
        EngineScore(centipawns=-100),
        12,
        82,
        MoveClassification.MISTAKE,
        GamePhase.OPENING,
        ("e2e4", "e7e5"),
        ("f2f3", "e7e5"),
        16,
        (Evidence("fact", "opening_development", "The center was neglected."),),
        ("opening_development",),
        True,
    )
    analysis = GameAnalysis(
        "coach-game",
        AnalysisProfile(engine_signature="Fake"),
        (move,),
        (1,),
        82,
        (PhaseSummary(GamePhase.OPENING, 82, 1, 1),),
    )
    return CoachPipeline().build(data(), analysis)


@pytest.fixture
def coach_window(
    app: QApplication, tmp_path: Path
) -> Iterator[tuple[MainWindow, FakeCoachRunner, GameData]]:
    game_data = data()
    database = GameDatabase(tmp_path / "games" / "games.sqlite3")
    assert database.save_game(game_data).success
    coach_runner = FakeCoachRunner()
    window = MainWindow(
        database=database,
        runner=FakeEngineRunner(),
        coach_runner=coach_runner,
        preference_settings=QSettings(
            str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat
        ),
    )
    window.setup.engine_path.setText("engine")
    window.show()
    yield window, coach_runner, game_data
    window.close()


def test_analysis_progress_result_and_review_reuse(
    coach_window: tuple[MainWindow, FakeCoachRunner, GameData],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, runner, game_data = coach_window
    monkeypatch.setattr(SavedGamesDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(SavedGamesDialog, "selected_game_id", lambda self: game_data.id)
    window.load_saved_game()
    window._load_selected_saved_game(window.destination_dialogs["games"])
    assert window.coach_panel.isVisible()
    window.coach_panel.analyze_button.click()
    assert runner.requests[-1][0] == game_data
    runner.progress.emit(AnalysisProgress(1, 2, "quick"))
    assert window.coach_panel.progress.value() == 1
    runner.result.emit(bundle())
    assert "Chess Coach accuracy: You 82.0%" in window.coach_panel.report.text()
    assert window.review.index == 0
    window.review_panel.next_key_button.click()
    assert window.review.index == 1
    assert "Mistake" in window.coach_panel.feedback.text()
    assert "82.0% move accuracy" in window.engine_label.text()
    assert window.review_panel.best_label.text() == "Engine best: e4"
    assert "Line: e4 e5" in window.coach_panel.feedback.text()
    assert "?" in window.history.item(0, 1).text()


def test_best_line_and_retry_restore_review(
    coach_window: tuple[MainWindow, FakeCoachRunner, GameData],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _, game_data = coach_window
    monkeypatch.setattr(SavedGamesDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(SavedGamesDialog, "selected_game_id", lambda self: game_data.id)
    window.load_saved_game()
    window._load_selected_saved_game(window.destination_dialogs["games"])
    window.coach_result(bundle())
    window.set_review_index(1)
    window.toggle_best_line()
    window.line_timer.stop()
    assert window.line_games
    assert window.review_panel.show_line_button.text() == "Hide Best Line"
    window.toggle_best_line()
    assert window.review_panel.show_line_button.text() == "Show Best Line"
    assert window.review.index == 1

    window.toggle_retry_move()
    assert window.retry_ply == 1
    assert window.board.best_highlight is None
    window.board.select_square(chess.G1)
    window.board.select_square(chess.H3)
    assert "misses the engine's main idea" in window.coach_panel.feedback.text()
    window.board.select_square(chess.E2)
    window.board.select_square(chess.E4)
    assert "Correct" in window.coach_panel.feedback.text()
    window.toggle_retry_move()
    assert window.retry_ply is None
    assert window.review.index == 1


def test_completed_match_has_one_click_review(app: QApplication, tmp_path: Path) -> None:
    game = parse_pgn("1. f3 e5 2. g4 Qh4# 0-1")
    database = GameDatabase(tmp_path / "games" / "games.sqlite3")
    coach_runner = FakeCoachRunner()
    window = MainWindow(
        game,
        database=database,
        runner=FakeEngineRunner(),
        coach_runner=coach_runner,
    )
    window.setup.engine_path.setText("engine")
    window.match = BotMatch(game, chess.WHITE, 1000)
    window.show()
    app.processEvents()
    window.refresh()
    assert window.review_game_button.isVisible()
    window.review_game_button.click()
    assert window.review is not None
    assert window.review.index == 0
    assert coach_runner.requests
    window.close()


def test_interactive_practice_and_lesson_completion(app: QApplication, tmp_path: Path) -> None:
    repository = CoachRepository(tmp_path / "games.sqlite3")
    result = bundle()
    repository.save_learning((), result.practice, result.lessons)
    practice = PracticeDialog(result.practice[0], repository)
    practice.board.select_square(chess.E2)
    practice.board.select_square(chess.E4)
    assert practice.prompt.text().startswith("Correct")
    assert repository.practice_items()[0].interval_days == 3
    lesson = LessonsDialog(result.lessons, repository)
    lesson._complete()
    assert "Completed" in lesson.content.text()
    assert repository.lessons()[0].completed
    practice.close()
    lesson.close()


def test_interrupted_analysis_is_offered_for_resume(
    coach_window: tuple[MainWindow, FakeCoachRunner, GameData],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _, game_data = coach_window
    run_id = window.coach_repository.start_run(game_data.id, AnalysisProfile())
    window.coach_repository.update_run(run_id, "cancelled", 1, 4)
    monkeypatch.setattr(SavedGamesDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(SavedGamesDialog, "selected_game_id", lambda self: game_data.id)
    window.load_saved_game()
    window._load_selected_saved_game(window.destination_dialogs["games"])
    assert window.coach_panel.analyze_button.text() == "Resume Analysis"
    assert "reuses every completed cached position" in window.coach_panel.feedback.text()


def test_practice_plays_reply_and_continues_line(app: QApplication, tmp_path: Path) -> None:
    repository = CoachRepository(tmp_path / "games.sqlite3")
    item = replace(bundle().practice[0], solution=("e2e4", "e7e5", "g1f3"))
    repository.save_learning((), (item,), ())
    dialog = PracticeDialog(item, repository)
    dialog.board.select_square(chess.E2)
    dialog.board.select_square(chess.E4)
    assert dialog.game.position.move_stack[-1].uci() == "e7e5"
    assert "Continue" in dialog.prompt.text()
    dialog.board.select_square(chess.G1)
    dialog.board.select_square(chess.F3)
    assert dialog.prompt.text().startswith("Correct")


def test_practice_mistake_returns_to_current_decision(app: QApplication, tmp_path: Path) -> None:
    repository = CoachRepository(tmp_path / "games.sqlite3")
    item = replace(bundle().practice[0], solution=("e2e4", "e7e5", "g1f3"))
    repository.save_learning((), (item,), ())
    dialog = PracticeDialog(item, repository)
    dialog.board.select_square(chess.E2)
    dialog.board.select_square(chess.E4)
    dialog.board.select_square(chess.G1)
    dialog.board.select_square(chess.H3)

    assert dialog.prompt.text().startswith("Mistake")
    assert dialog.session.solution_index == 2
    assert dialog.board.game.position.move_stack[-1].uci() == "g1h3"

    dialog.mistake_timer.stop()
    dialog._restore_after_mistake()
    expected_fen = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2").fen()
    assert dialog.board.game.fen == expected_fen
    dialog.board.select_square(chess.G1)
    dialog.board.select_square(chess.F3)
    assert dialog.prompt.text().startswith("Correct")
    assert repository.practice_progress().successful == 1
    dialog.close()


def test_learning_dashboards_and_lesson_resume(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game_data = data()
    database = GameDatabase(tmp_path / "games.sqlite3")
    assert database.save_game(game_data).success
    repository = CoachRepository(database.path)
    result = bundle()
    repository.save_learning(
        tuple(),
        result.practice,
        result.lessons,
    )
    analysis_run = repository.start_run(game_data.id, result.analysis.profile)
    repository.save_analysis(analysis_run, result.analysis)
    CoachPipeline(repository).build(game_data, result.analysis)

    dashboard = WeaknessDashboardDialog(repository)
    assert dashboard.table.rowCount() >= 1
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Yes)
    dashboard.dismiss_button.click()
    assert dashboard.table.rowCount() == 0

    queue = PracticeQueueDialog(repository)
    assert "Due today:" in queue.progress.text()
    assert queue.table.rowCount() >= 1

    lessons = repository.lessons()
    dialog = LessonsDialog(lessons, repository)
    dialog.next.click()
    dialog.next.click()
    assert dialog.step == 2
    assert not dialog.example_board.isHidden()
    dialog.close()
    reopened = LessonsDialog(repository.lessons(), repository)
    assert reopened.step == 2


def test_review_preferences_control_board_and_analysis(app: QApplication, tmp_path: Path) -> None:
    store = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    preferences = UserPreferences(
        board_orientation="black",
        board_theme="high_contrast",
        analysis_profile="quick",
        review_perspective="both",
        show_best_move=False,
        coach_verbosity="concise",
    )
    preferences.save(store)
    runner = FakeCoachRunner()
    window = MainWindow(
        database=GameDatabase(tmp_path / "games.sqlite3"),
        runner=FakeEngineRunner(),
        coach_runner=runner,
        preference_settings=store,
    )
    window.setup.engine_path.setText("engine")
    window.open_review(data())
    window.coach_result(bundle())
    window.set_review_index(1)

    assert window.board.orientation == chess.BLACK
    assert window.board.theme == "high_contrast"
    assert window.board.best_highlight is None
    assert window.coach_panel.filter.currentData() == "both"
    assert "Line:" not in window.coach_panel.feedback.text()
    window.start_coach_analysis()
    assert runner.requests[-1][4].name == "quick"
    window.close()
