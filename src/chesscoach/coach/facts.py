"""Deterministic evidence extracted from legal board states."""

import chess

from chesscoach.coach.models import Evidence, GamePhase
from chesscoach.coach.scoring import game_phase

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def _fork_targets(board: chess.Board, square: chess.Square, color: chess.Color) -> tuple[str, ...]:
    targets = []
    for target in board.attacks(square):
        piece = board.piece_at(target)
        if piece and piece.color != color and PIECE_VALUES.get(piece.piece_type, 0) >= 3:
            targets.append(chess.square_name(target))
    return tuple(sorted(targets))


def extract_evidence(
    board: chess.Board, played: chess.Move, best: chess.Move
) -> tuple[Evidence, ...]:
    if played not in board.legal_moves or best not in board.legal_moves:
        raise ValueError("Evidence requires legal played and best moves.")
    facts: list[Evidence] = []
    mover = board.turn
    captured = board.piece_at(played.to_square)
    played_san = board.san(played)
    best_san = board.san(best)
    after = board.copy()
    after.push(played)
    moved_piece = after.piece_at(played.to_square)
    attackers = after.attackers(not mover, played.to_square)
    defenders = after.attackers(mover, played.to_square)
    if moved_piece and moved_piece.piece_type != chess.KING and attackers and not defenders:
        facts.append(
            Evidence(
                "played-piece-hanging",
                "hanging_piece",
                f"After {played_san}, the moved "
                f"{chess.piece_name(moved_piece.piece_type)} is attacked and undefended.",
                (chess.square_name(played.to_square),),
            )
        )
    if captured:
        facts.append(
            Evidence(
                "played-capture",
                "material",
                f"{played_san} captures a {chess.piece_name(captured.piece_type)}.",
                (chess.square_name(played.to_square),),
            )
        )
    if after.is_check():
        facts.append(Evidence("played-check", "check", f"{played_san} gives check."))
    forked = _fork_targets(after, played.to_square, mover)
    if len(forked) >= 2:
        facts.append(
            Evidence(
                "played-fork",
                "fork",
                f"{played_san} attacks multiple valuable pieces.",
                forked,
            )
        )
        if moved_piece and moved_piece.piece_type == chess.KNIGHT:
            facts.append(
                Evidence(
                    "played-knight-tactic",
                    "knight_tactics",
                    f"{played_san} uses a knight to attack multiple valuable pieces.",
                    forked,
                )
            )
    before_pins = {
        sq for sq in chess.SQUARES if board.piece_at(sq) and board.is_pinned(not mover, sq)
    }
    after_pins = {
        sq for sq in chess.SQUARES if after.piece_at(sq) and after.is_pinned(not mover, sq)
    }
    new_pins = tuple(chess.square_name(square) for square in sorted(after_pins - before_pins))
    if new_pins:
        facts.append(Evidence("played-pin", "pin", f"{played_san} creates a pin.", new_pins))

    if played != best:
        best_after = board.copy()
        best_capture = best_after.piece_at(best.to_square)
        best_after.push(best)
        if best_after.is_check():
            facts.append(
                Evidence("missed-check", "calculation", f"Stockfish's {best_san} gives check.")
            )
        best_fork = _fork_targets(best_after, best.to_square, mover)
        if len(best_fork) >= 2:
            facts.append(
                Evidence(
                    "missed-fork",
                    "fork",
                    f"Stockfish's {best_san} creates a fork.",
                    best_fork,
                )
            )
            best_piece = board.piece_at(best.from_square)
            if best_piece and best_piece.piece_type == chess.KNIGHT:
                facts.append(
                    Evidence(
                        "missed-knight-tactic",
                        "knight_tactics",
                        f"Stockfish's {best_san} creates a knight fork.",
                        best_fork,
                    )
                )
        if best_capture and not captured:
            facts.append(
                Evidence(
                    "missed-capture",
                    "material",
                    f"Stockfish's {best_san} captures a "
                    f"{chess.piece_name(best_capture.piece_type)}.",
                    (chess.square_name(best.to_square),),
                )
            )
    if (
        game_phase(board) == GamePhase.OPENING
        and moved_piece
        and moved_piece.piece_type
        in (
            chess.KNIGHT,
            chess.BISHOP,
        )
    ):
        facts.append(
            Evidence("development", "opening_development", f"{played_san} develops a minor piece.")
        )
    phase = game_phase(board)
    if phase == GamePhase.OPENING:
        facts.append(
            Evidence(
                "opening-context",
                "opening_principles",
                "This opening decision affects development, central control, or king safety.",
            )
        )
    elif phase == GamePhase.ENDGAME:
        facts.append(
            Evidence(
                "endgame-context",
                "endgame",
                "King activity and pawn promotion are central in this endgame.",
            )
        )
    if not facts:
        facts.append(
            Evidence(
                "engine-comparison",
                "calculation",
                f"Stockfish prefers {best_san} to {played_san} based on the "
                "resulting continuations.",
            )
        )
    return tuple(facts)
