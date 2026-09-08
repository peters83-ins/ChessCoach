import chess

from chesscoach.coach.facts import extract_evidence


def test_hanging_piece_is_grounded_in_board_attacks() -> None:
    board = chess.Board("4k3/8/p7/8/2B5/8/8/4K3 w - - 0 1")
    facts = extract_evidence(board, chess.Move.from_uci("c4b5"), chess.Move.from_uci("c4d3"))
    hanging = next(fact for fact in facts if fact.tag == "hanging_piece")
    assert hanging.squares == ("b5",)
    assert "attacked and undefended" in hanging.summary


def test_illegal_moves_cannot_produce_evidence() -> None:
    board = chess.Board()
    try:
        extract_evidence(board, chess.Move.from_uci("e2e5"), chess.Move.from_uci("e2e4"))
    except ValueError as error:
        assert "legal" in str(error)
    else:
        raise AssertionError("Illegal evidence input was accepted")
