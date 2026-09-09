from pathlib import Path

from PySide6.QtWidgets import QApplication

from chesscoach.coach.models import WeaknessEvent
from chesscoach.courses.catalog import CourseCatalog
from chesscoach.storage.coach import CoachRepository
from chesscoach.storage.database import GameDatabase
from chesscoach.ui.insights import InsightsDialog


def test_insights_panel_has_local_summary_and_empty_chart(
    app: QApplication, tmp_path: Path
) -> None:
    dialog = InsightsDialog(
        CoachRepository(tmp_path / "coach.sqlite3"), GameDatabase(tmp_path / "games.sqlite3")
    )
    assert "local Chess Coach estimates" in dialog.summary.text()
    assert dialog.openings.rowCount() == 0
    assert dialog.themes.rowCount() == 0
    assert "five qualifying" in dialog.transfer.text()
    assert dialog.mastery.value() == 0
    assert not dialog.practice_theme.isEnabled()
    assert not dialog.course_theme.isEnabled()
    dialog.close()


def test_insights_opens_a_supporting_position_for_a_theme(
    app: QApplication, tmp_path: Path
) -> None:
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    repository.save_learning(
        (WeaknessEvent("default", "game-1", 7, "fork", 2.0, 1.0),), (), ()
    )
    dialog = InsightsDialog(repository, GameDatabase(tmp_path / "games.sqlite3"))
    assert dialog.themes.rowCount() == 1
    assert dialog.open_example.isEnabled() is False

    received: list[tuple[str, int]] = []
    dialog.example_requested.connect(lambda game_id, ply: received.append((game_id, ply)))
    dialog.themes.selectRow(0)
    assert dialog.open_example.isEnabled()
    dialog.open_example.click()
    assert received == [("game-1", 7)]
    dialog.close()


def test_insights_links_theme_to_matching_course(
    app: QApplication, tmp_path: Path
) -> None:
    repository = CoachRepository(tmp_path / "coach.sqlite3")
    repository.save_learning(
        (WeaknessEvent("default", "game-1", 2, "development", 1.0, 1.0),), (), ()
    )
    dialog = InsightsDialog(
        repository, GameDatabase(tmp_path / "games.sqlite3"), CourseCatalog.built_in()
    )
    dialog.themes.selectRow(0)
    assert dialog.course_theme.isEnabled()
    received: list[str] = []
    dialog.theme_course_requested.connect(received.append)
    dialog.course_theme.click()
    assert received == ["development"]
    dialog.close()
