from pathlib import Path

from PySide6.QtWidgets import QApplication

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
    dialog.close()
