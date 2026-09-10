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
    games = parse_pgn_games(text)
    if not games:
        raise ValueError("PGN is empty or contains invalid moves.")
    return games[0]


def parse_pgn_games(text: str) -> tuple[Game, ...]:
    """Parse every standard mainline game in a PGN document."""
    stream = io.StringIO(text)
    games: list[Game] = []
    while record := chess.pgn.read_game(stream):
        if record.errors:
            raise ValueError("PGN contains invalid moves.")
        if record.headers.get("Variant", "Standard").lower() not in (
            "standard",
            "chess",
            "normal",
        ):
            raise ValueError("Only standard chess PGN is supported.")
        game = Game(record.board().fen())
        move_count = 0
        for move in record.mainline_moves():
            if not game.attempt_move(move):
                raise ValueError("PGN contains an illegal move or continues after game over.")
            move_count += 1
        if move_count == 0:
            raise ValueError("PGN game contains no moves.")
        games.append(game)
    return tuple(games)


def export_pgn_games(games: Iterable[Game]) -> str:
    """Export multiple games separated by the standard PGN blank line."""
    return "\n\n".join(export_pgn(game).rstrip() for game in games)


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
