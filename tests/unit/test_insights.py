from datetime import UTC, datetime, timedelta

from chesscoach.chess.openings import OpeningMatch
from chesscoach.coach.insights import (
    analyzed_theme_counts,
    compare_analysis_profiles,
    opening_departure_transfer,
    opening_stats,
    period_comparison,
    phase_accuracy,
    phase_transfer,
    recency_weighted_average,
    recommend_next_action,
    theme_frequency,
    transfer_metric,
)
from chesscoach.coach.models import EngineScore, GamePhase, MoveAnalysis, MoveClassification


def test_compare_analysis_profiles_groups_cached_runs():
    result = compare_analysis_profiles((("quick", 80.0), ("quick", 90.0), ("deep", 100.0)))
    assert [(item.profile, item.runs, item.mean_accuracy) for item in result] == [
        ("deep", 1, 100.0),
        ("quick", 2, 85.0),
    ]


def test_opening_stats_require_five_games():
    opening = OpeningMatch("C50", "Italian Game")
    records = tuple((opening, "1-0", "white") for _ in range(4))
    assert opening_stats(records) == ()
    assert opening_stats(records + ((opening, "0-1", "white"),))[0].games == 5


def test_recency_weights_recent_results_more():
    now = datetime(2026, 1, 31, tzinfo=UTC)
    result = recency_weighted_average(((100.0, now), (0.0, now - timedelta(days=90))), now)
    assert result > 50


def test_period_comparison_requires_both_periods_and_weights_recent():
    now = datetime(2026, 1, 31, tzinfo=UTC)
    values = tuple((1.0, now - timedelta(days=days)) for days in (1, 10, 30, 60, 90, 120))
    comparison = period_comparison(values, now=now)
    assert comparison is not None
    recent, prior = comparison
    assert recent == 1.0 and prior == 1.0
    assert period_comparison(values[:4], now=now) is None


def test_recommendation_prioritizes_due_then_weakness():
    assert recommend_next_action(3, "fork", 10).startswith("Complete 3")
    assert "fork" in recommend_next_action(0, "fork", 10)
    assert "latest" in recommend_next_action(0, "", 2)


def test_theme_frequency_and_transfer_threshold():
    assert theme_frequency(("fork", "pin", "fork")) == (("fork", 2), ("pin", 1))
    assert transfer_metric("fork", (True,) * 4, (True,) * 5) is None
    metric = transfer_metric("fork", (False,) * 5, (True,) * 5)
    assert metric is not None and metric.delta == 1.0


def test_phase_and_analyzed_theme_aggregations():
    move = MoveAnalysis(
        1,
        "fen",
        "white",
        "e2e4",
        "e4",
        "e2e4",
        "e4",
        EngineScore(10),
        EngineScore(10),
        0,
        90,
        MoveClassification.BEST,
        GamePhase.OPENING,
        (),
        (),
        10,
        tags=("development",),
    )
    assert phase_accuracy((move,), "white") == (("opening", 90, 1),)
    assert analyzed_theme_counts((move,)) == (("development", 1),)


def test_phase_transfer_requires_recent_and_prior_samples():
    now = datetime(2026, 1, 31, tzinfo=UTC)
    records = tuple(
        [("opening", 90.0, now - timedelta(days=days)) for days in (1, 2, 3)]
        + [("opening", 60.0, now - timedelta(days=60 + days)) for days in (1, 2, 3)]
    )
    result = phase_transfer(records, now=now)
    assert result == (("opening", 90.0, 60.0, 6),)


def test_opening_departure_transfer_requires_recognized_games():
    now = datetime(2026, 1, 31, tzinfo=UTC)
    recent = tuple(
        (("e2e4", "e7e5", "g1f3", "b8c6", "f1c4"), now - timedelta(days=days))
        for days in (1, 2, 3)
    )
    prior = tuple(
        (("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "a7a6", "a2a3"), now - timedelta(days=60 + days))
        for days in (1, 2, 3)
    )
    result = opening_departure_transfer(recent + prior, now=now)
    assert result == (1.0, 5 / 7, 6)
