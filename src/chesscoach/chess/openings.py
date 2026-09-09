"""Small reviewed opening book for local recognition and aggregate records."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class OpeningMatch:
    eco: str
    name: str
    variation: str = ""
    book_plies: int = 0

    @property
    def display_name(self) -> str:
        return f"{self.name}: {self.variation}" if self.variation else self.name


@dataclass(frozen=True)
class OpeningStatistic:
    opening: str
    games: int
    wins: int
    draws: int
    losses: int


# Longest matching line wins. Generic first-move entries provide a useful fallback.
OPENING_LINES: tuple[tuple[tuple[str, ...], str, str, str], ...] = (
    (("e2e4", "e7e5", "g1f3", "b8c6", "f1b5"), "C60", "Ruy Lopez", ""),
    (("e2e4", "e7e5", "g1f3", "b8c6", "f1c4"), "C50", "Italian Game", ""),
    (("e2e4", "e7e5", "g1f3", "g8f6"), "C42", "Petrov Defense", ""),
    (("e2e4", "e7e5", "f2f4"), "C30", "King's Gambit", ""),
    (("e2e4", "c7c5", "g1f3", "d7d6"), "B50", "Sicilian Defense", "Modern"),
    (("e2e4", "c7c5", "g1f3", "b8c6"), "B30", "Sicilian Defense", "Open"),
    (("e2e4", "c7c5"), "B20", "Sicilian Defense", ""),
    (("e2e4", "e7e6"), "C00", "French Defense", ""),
    (("e2e4", "c7c6"), "B10", "Caro-Kann Defense", ""),
    (("e2e4", "d7d5"), "B01", "Scandinavian Defense", ""),
    (("d2d4", "d7d5", "c2c4", "e7e6"), "D30", "Queen's Gambit", "Declined"),
    (("d2d4", "d7d5", "c2c4", "d5c4"), "D20", "Queen's Gambit", "Accepted"),
    (("d2d4", "g8f6", "c2c4", "g7g6"), "E60", "King's Indian Defense", ""),
    (("d2d4", "g8f6", "c2c4", "e7e6", "b1c3", "f8b4"), "E20", "Nimzo-Indian Defense", ""),
    (("d2d4", "g8f6", "c2c4", "c7c5", "d4d5"), "A56", "Benoni Defense", ""),
    (("c2c4",), "A10", "English Opening", ""),
    (("g1f3",), "A04", "Reti Opening", ""),
    (("e2e4",), "B00", "King's Pawn Opening", ""),
    (("d2d4",), "A40", "Queen's Pawn Opening", ""),
)


def recognize_opening(moves: tuple[str, ...]) -> OpeningMatch | None:
    """Return the longest reviewed opening prefix matching a game."""
    matches = [line for line in OPENING_LINES if moves[: len(line[0])] == line[0]]
    if not matches:
        return None
    sequence, eco, name, variation = max(matches, key=lambda line: len(line[0]))
    return OpeningMatch(eco, name, variation, len(sequence))


def aggregate_openings(
    records: Iterable[tuple[OpeningMatch, str, str]], *, min_games: int = 3
) -> tuple[OpeningStatistic, ...]:
    """Aggregate learner results, omitting samples too small to characterize."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for opening, result, player_color in records:
        if result == "1/2-1/2":
            outcome = "draw"
        else:
            won = (result == "1-0") == (player_color == "white")
            outcome = "win" if won else "loss"
        grouped[opening.display_name].append(outcome)
    return tuple(
        OpeningStatistic(
            name, len(results), results.count("win"), results.count("draw"), results.count("loss")
        )
        for name, results in sorted(grouped.items())
        if len(results) >= min_games
    )
