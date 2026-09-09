from datetime import UTC, datetime, timedelta

from chesscoach.chess.openings import OpeningMatch
from chesscoach.coach.insights import (
    opening_stats,
    recency_weighted_average,
    recommend_next_action,
    theme_frequency,
    transfer_metric,
)


def test_opening_stats_require_five_games():
    opening = OpeningMatch("C50", "Italian Game")
    records = tuple((opening, "1-0", "white") for _ in range(4))
    assert opening_stats(records) == ()
    assert opening_stats(records + ((opening, "0-1", "white"),))[0].games == 5


def test_recency_weights_recent_results_more():
    now = datetime(2026, 1, 31, tzinfo=UTC)
    result = recency_weighted_average(((100.0, now), (0.0, now - timedelta(days=90))), now)
    assert result > 50


def test_recommendation_prioritizes_due_then_weakness():
    assert recommend_next_action(3, "fork", 10).startswith("Complete 3")
    assert "fork" in recommend_next_action(0, "fork", 10)
    assert "latest" in recommend_next_action(0, "", 2)


def test_theme_frequency_and_transfer_threshold():
    assert theme_frequency(("fork", "pin", "fork")) == (("fork", 2), ("pin", 1))
    assert transfer_metric("fork", (True,) * 4, (True,) * 5) is None
    metric = transfer_metric("fork", (False,) * 5, (True,) * 5)
    assert metric is not None and metric.delta == 1.0
