"""PGN text interchange, independent of the board widget."""

import io
from collections.abc import Iterable

import chess
import chess.pgn

from chesscoach.chess.game import Game


def export_pgn(game: Game) -> str:
    record = chess.pgn.Game.from_board(game.position)
    record.headers["Result"] = game.status().result
    return str(record)


def parse_pgn(text: str) -> Game:
    """Load the first standard game mainline, rejecting partial/illegal input.

    Comments, variations, and headers are not retained. Recorded resignations and
    agreed draws do not end the reconstructed playable position.
    """
    record = chess.pgn.read_game(io.StringIO(text))
    if record is None or record.errors:
        raise ValueError("PGN is empty or contains invalid moves.")
    if record.headers.get("Variant", "Standard").lower() not in ("standard", "chess", "normal"):
        raise ValueError("Only standard chess PGN is supported.")
    game = Game(record.board().fen())
    for move in record.mainline_moves():
        if not game.attempt_move(move):
            raise ValueError("PGN contains an illegal move or continues after game over.")
    return game


def san_variation(fen: str, moves: Iterable[str]) -> str:
    """Format the legal prefix of a UCI variation as readable SAN."""
    board = chess.Board(fen)
    notation = []
    for uci in moves:
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            break
        notation.append(board.san(move))
        board.push(move)
    return " ".join(notation)
