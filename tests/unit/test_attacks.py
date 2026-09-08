import chess

from chesscoach.chess.attacks import attack_pairs


def test_attacks_include_enemy_targets_only() -> None:
    assert attack_pairs(chess.Board()) == ()
    board = chess.Board("7k/8/8/3p4/4P3/8/8/K7 w - - 0 1")
    assert set(attack_pairs(board)) == {(chess.E4, chess.D5), (chess.D5, chess.E4)}


def test_pinned_attacker_is_geometric_not_legal_capture() -> None:
    board = chess.Board("k3r3/8/8/8/8/8/3qR3/4K3 w - - 0 1")
    assert (chess.E2, chess.D2) in attack_pairs(board)
    assert chess.Move(chess.E2, chess.D2) not in board.legal_moves
