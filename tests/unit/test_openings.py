from chesscoach.chess.openings import OpeningMatch, aggregate_openings, recognize_opening


def test_recognition_uses_longest_reviewed_line() -> None:
    opening = recognize_opening(("e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"))
    assert opening is not None
    assert (opening.eco, opening.display_name, opening.book_plies) == ("C60", "Ruy Lopez", 5)
    assert recognize_opening(("a2a3",)) is None


def test_opening_statistics_require_meaningful_sample() -> None:
    opening = OpeningMatch("B20", "Sicilian Defense")
    records = (
        (opening, "1-0", "white"),
        (opening, "0-1", "white"),
        (opening, "1/2-1/2", "black"),
    )
    assert aggregate_openings(records, min_games=4) == ()
    statistic = aggregate_openings(records)[0]
    assert (statistic.games, statistic.wins, statistic.draws, statistic.losses) == (3, 1, 1, 1)
