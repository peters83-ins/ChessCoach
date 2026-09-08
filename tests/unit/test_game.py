import chess
import pytest

from chesscoach.chess.game import Game


def play(game: Game, *moves: str) -> None:
    for move in moves:
        assert game.attempt_move(chess.Move.from_uci(move))


def test_initial_position_and_isolation() -> None:
    game = Game()
    assert game.fen == chess.STARTING_FEN
    assert game.turn == chess.WHITE
    assert len(list(game.position.legal_moves)) == 20
    assert game.history() == ()
    board = game.position
    board.push_uci("e2e4")
    assert game.fen == chess.STARTING_FEN
    assert not game.undo()
    assert not game.claim_draw()


def test_moves_turns_captures_history_and_undo() -> None:
    game = Game()
    initial = game.fen
    assert not game.attempt_move(chess.Move.from_uci("e2e5"))
    assert not game.attempt_move(chess.Move.from_uci("e7e5"))
    assert game.fen == initial
    assert {m.uci() for m in game.legal_moves_from(chess.E2)} == {"e2e3", "e2e4"}
    play(game, "e2e4")
    assert game.turn == chess.BLACK
    play(game, "d7d5")
    before_capture = game.fen
    play(game, "e4d5")
    assert game.piece_at(chess.D5) == chess.Piece(chess.PAWN, chess.WHITE)
    assert len(game.position.piece_map()) == 31
    assert [m.san for m in game.history()] == ["e4", "d5", "exd5"]
    assert game.undo()
    assert game.fen == before_capture
    assert [m.san for m in game.history()] == ["e4", "d5"]
    game.reset()
    assert game.fen == chess.STARTING_FEN
    assert game.history() == ()
    assert not game.can_undo


@pytest.mark.parametrize(
    ("move", "king", "rook"), [("e1g1", chess.G1, chess.F1), ("e1c1", chess.C1, chess.D1)]
)
def test_castling(move: str, king: int, rook: int) -> None:
    game = Game("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    before = game.fen
    play(game, move)
    assert game.piece_at(king) == chess.Piece(chess.KING, chess.WHITE)
    assert game.piece_at(rook) == chess.Piece(chess.ROOK, chess.WHITE)
    assert game.undo()
    assert game.fen == before


def test_cannot_castle_through_check_or_expose_king() -> None:
    game = Game("4kr2/8/8/8/8/8/8/4K2R w K - 0 1")
    assert not game.attempt_move(chess.Move.from_uci("e1g1"))
    game = Game("k3r3/8/8/8/8/8/4R3/4K3 w - - 0 1")
    assert not game.attempt_move(chess.Move.from_uci("e2d2"))


def test_en_passant_and_undo() -> None:
    game = Game()
    play(game, "e2e4", "a7a6", "e4e5", "d7d5")
    before = game.fen
    play(game, "e5d6")
    assert game.piece_at(chess.D5) is None
    assert game.piece_at(chess.D6) == chess.Piece(chess.PAWN, chess.WHITE)
    assert game.history()[-1].san == "exd6"
    game.undo()
    assert game.fen == before


@pytest.mark.parametrize("promotion", [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT])
@pytest.mark.parametrize(
    ("fen", "source", "target", "color"),
    [
        ("7k/P7/8/8/8/8/8/7K w - - 0 1", chess.A7, chess.A8, chess.WHITE),
        ("7k/8/8/8/8/8/p7/7K b - - 0 1", chess.A2, chess.A1, chess.BLACK),
    ],
)
def test_promotion(fen: str, source: int, target: int, color: bool, promotion: int) -> None:
    game = Game(fen)
    assert not game.attempt_move(chess.Move(source, target))
    assert game.attempt_move(chess.Move(source, target, promotion))
    assert game.piece_at(target) == chess.Piece(promotion, color)
    assert "=" in game.history()[-1].san
    game.undo()
    assert game.fen == fen


def test_check_checkmate_and_undo_game_over() -> None:
    game = Game("7k/8/8/8/8/8/8/KR6 w - - 0 1")
    play(game, "b1b8")
    assert game.status().in_check
    assert not game.status().game_over
    assert "check" in game.status().message
    game.reset()
    play(game, "f2f3", "e7e5", "g2g4", "d8h4")
    assert game.status().game_over
    assert game.status().result == "0-1"
    assert game.status().message == "Checkmate — Black wins"
    assert game.legal_moves_from(chess.E2) == ()
    assert not game.attempt_move(chess.Move.from_uci("e2e4"))
    assert game.history()[-1].san == "Qh4#"
    game.undo()
    assert not game.status().game_over


@pytest.mark.parametrize(
    ("fen", "reason"),
    [
        ("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", "stalemate"),
        ("7k/8/8/8/8/8/8/K7 w - - 0 1", "insufficient material"),
        ("7k/8/8/8/8/8/8/KR6 w - - 150 76", "seventyfive moves"),
    ],
)
def test_automatic_draws(fen: str, reason: str) -> None:
    game = Game(fen)
    assert game.status().game_over
    assert game.status().result == "1/2-1/2"
    assert reason in game.status().message


def test_repetition_claim_and_automatic_fivefold() -> None:
    game = Game()
    cycle = ("g1f3", "g8f6", "f3g1", "f6g8")
    play(game, *cycle, *cycle)
    assert game.status().can_claim_draw
    assert not game.status().game_over
    assert game.claim_draw()
    assert game.status().game_over
    assert game.status().result == "1/2-1/2"
    assert not game.claim_draw()
    game.undo()
    assert not game.status().game_over
    assert len(game.history()) == 8
    play(game, *cycle, *cycle)
    assert game.status().game_over
    assert "fivefold repetition" in game.status().message


def test_fifty_move_claim() -> None:
    game = Game("7k/8/8/8/8/8/8/KR6 w - - 100 51")
    assert game.claim_draw()
    game.reset()
    assert not game.status().game_over


def test_invalid_position() -> None:
    with pytest.raises(ValueError):
        Game("8/8/8/8/8/8/8/8 w - - 0 1")
