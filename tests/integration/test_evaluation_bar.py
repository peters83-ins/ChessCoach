import chess
import chess.engine
import pytest
from PySide6.QtWidgets import QApplication

from chesscoach.ui.evaluation_bar import EvaluationBar, white_score_fraction


def score(centipawns: int) -> chess.engine.PovScore:
    return chess.engine.PovScore(chess.engine.Cp(centipawns), chess.WHITE)


@pytest.mark.parametrize(
    ("centipawns", "minimum", "maximum"),
    [(-250, 0.30, 0.32), (0, 0.49, 0.51), (250, 0.68, 0.70)],
)
def test_score_controls_white_share(centipawns: int, minimum: float, maximum: float) -> None:
    assert minimum < white_score_fraction(score(centipawns)) < maximum


def test_evaluation_bar_score_result_and_orientation(app: QApplication) -> None:
    bar = EvaluationBar()
    bar.set_score(score(250))
    assert bar.white_fraction > 0.5
    assert bar.display_text == "+2.5"
    assert "+2.5" in bar.accessibleName()
    bar.resize(34, 200)
    bar.show()
    app.processEvents()
    image = bar.grab().toImage()
    assert image.pixelColor(28, 10).lightness() < image.pixelColor(28, 190).lightness()

    bar.set_orientation(False)
    app.processEvents()
    assert not bar.white_at_bottom
    image = bar.grab().toImage()
    assert image.pixelColor(28, 10).lightness() > image.pixelColor(28, 190).lightness()
    bar.set_result(chess.BLACK)
    assert bar.white_fraction == 0.02
    assert bar.display_text == "0-1"
    bar.clear()
    assert bar.white_fraction == 0.5


def test_mate_fills_winning_side() -> None:
    white_mate = chess.engine.PovScore(chess.engine.Mate(3), chess.WHITE)
    black_mate = chess.engine.PovScore(chess.engine.Mate(-2), chess.WHITE)
    assert white_score_fraction(white_mate) == 0.98
    assert white_score_fraction(black_mate) == 0.02
