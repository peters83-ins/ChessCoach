"""PGN text interchange, independent of the board widget."""

import io

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
