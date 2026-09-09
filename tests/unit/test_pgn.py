import chess
import pytest

from chesscoach.chess.game import Game
from chesscoach.chess.pgn import export_pgn, parse_pgn, san_variation


def test_pgn_roundtrip() -> None:
    game = parse_pgn("1. e4 e5 2. Nf3 Nc6 *")
    text = export_pgn(game)
    assert "1. e4 e5 2. Nf3 Nc6 *" in text
    restored = parse_pgn(text)
    assert restored.fen == game.fen
    assert restored.history() == game.history()
    restored.undo()
    assert len(restored.history()) == 3


def test_custom_position_roundtrip_and_black_numbering() -> None:
    game = Game("7k/8/8/8/8/8/8/KR6 b - - 0 23")
    assert game.attempt_move(chess.Move.from_uci("h8g8"))
    text = export_pgn(game)
    assert '[SetUp "1"]' in text
    assert "23... Kg8" in text
    assert parse_pgn(text).fen == game.fen
    assert game.history()[0].number == 23
    assert game.history()[0].color == chess.BLACK


def test_export_results() -> None:
    game = parse_pgn("1. f3 e5 2. g4 Qh4# 0-1")
    assert '[Result "0-1"]' in export_pgn(game)
    game = Game("7k/8/8/8/8/8/8/KR6 w - - 100 51")
    game.claim_draw()
    assert '[Result "1/2-1/2"]' in export_pgn(game)


@pytest.mark.parametrize("text", ["", "1. e4 e5 2. Bh6 *", '[Variant "Atomic"]\n\n*'])
def test_reject_bad_pgn(text: str) -> None:
    with pytest.raises(ValueError):
        parse_pgn(text)


def test_san_variation_formats_only_legal_prefix() -> None:
    assert san_variation(chess.STARTING_FEN, ("e2e4", "e7e5", "e1e8")) == "e4 e5"
