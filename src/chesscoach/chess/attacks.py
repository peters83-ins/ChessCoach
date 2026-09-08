"""Geometric attacks on occupied enemy squares, not a tactical verdict.

Pinned attackers are included by python-chess. This is not a list of legal captures
and does not promise that a capture wins material. En passant has no occupied target.
"""

import chess


def attack_pairs(position: chess.Board) -> tuple[tuple[chess.Square, chess.Square], ...]:
    return tuple(
        (source, target)
        for source, piece in sorted(position.piece_map().items())
        for target in position.attacks(source)
        if (victim := position.piece_at(target)) is not None and victim.color != piece.color
    )
