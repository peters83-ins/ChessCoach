from dataclasses import replace

import chess

from chesscoach.coach.models import PracticeItem
from chesscoach.coach.practice import generate_practice_items
from chesscoach.coach.training import TrainingSession
from tests.unit.test_coach_learning import mistake


def item(**changes: object) -> PracticeItem:
    values: dict[str, object] = {
        "id": "item",
        "profile_id": "default",
        "source_game_id": "game",
        "source_ply": 1,
        "fen": chess.STARTING_FEN,
        "theme": "calculation",
        "solution": ("e2e4", "e7e5", "g1f3"),
    }
    values.update(changes)
    return PracticeItem(**values)


def test_wrong_move_rolls_back_only_current_decision() -> None:
    session = TrainingSession(item())
    first = session.attempt(chess.Move.from_uci("e2e4"))
    assert first.correct and first.forced_reply == "e7e5"
    assert (
        session.game.fen
        == chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2").fen()
    )

    mistake_result = session.attempt(chess.Move.from_uci("g1h3"))
    assert mistake_result.mistake and mistake_result.decision_index == 1
    assert session.solution_index == 2
    assert session.game.fen == first.rollback_fen

    final = session.attempt(chess.Move.from_uci("g1f3"))
    assert final.completed


def test_alternative_line_is_accepted_at_each_decision() -> None:
    session = TrainingSession(
        item(
            alternative_lines=(("d2d4", "d7d5", "c2c4"),),
        )
    )
    result = session.attempt(chess.Move.from_uci("d2d4"))
    assert result.correct and result.forced_reply == "d7d5"
    assert session.attempt(chess.Move.from_uci("c2c4")).completed


def test_generated_practice_lines_are_short() -> None:
    long_move = replace(mistake(), best_pv=("e2e4", "e7e5", "g1f3", "b8c6"))
    items = generate_practice_items("default", "game", (long_move,))
    assert len(items[0].solution) <= 3
