"""Reviewed local lesson templates personalized with game examples."""

from uuid import NAMESPACE_URL, uuid5

from chesscoach.coach.models import Lesson, PracticeItem, WeaknessScore

LESSON_TEMPLATES = {
    "hanging_piece": (
        "Protect Loose Pieces",
        "A piece is loose when the opponent can attack or capture it without an adequate reply.",
        ("Scan every attacked piece.", "Count attackers and defenders before committing."),
        "Moving a piece to an attacked, undefended square.",
    ),
    "fork": (
        "Knight and Piece Forks",
        "A fork makes one piece attack two or more valuable targets at once.",
        ("Check forcing jumps first.", "Look for king-and-queen or king-and-rook targets."),
        "Checking one threat without noticing the second target.",
    ),
    "opening_development": (
        "Efficient Development",
        "Develop pieces toward useful squares while preparing king safety.",
        ("Move minor pieces once when possible.", "Connect rooks by clearing the back rank."),
        "Repeating moves while undeveloped pieces remain at home.",
    ),
    "opening_principles": (
        "Opening Priorities",
        "Fight for the center, develop efficiently, and secure the king before attacking.",
        ("Count undeveloped pieces.", "Check whether the king can castle safely."),
        "Starting flank operations while the center and king remain unresolved.",
    ),
    "knight_tactics": (
        "Knight Tactical Patterns",
        "Knight jumps cannot be blocked and can attack several valuable targets.",
        ("Map every checking jump.", "Look for two valuable targets of one knight."),
        "Seeing the first attacked piece while overlooking a second fork target.",
    ),
    "endgame": (
        "Endgame Priorities",
        "Activate the king and calculate pawn races before making distant piece moves.",
        ("Count moves to promotion.", "Bring the king toward passed pawns."),
        "Keeping the king passive after queens and major pieces are exchanged.",
    ),
    "calculation": (
        "Forcing-Move Calculation",
        "Calculate checks, captures, and direct threats before quieter moves.",
        ("List forcing candidates.", "Check the opponent's strongest reply."),
        "Stopping the calculation after your own intended move.",
    ),
    "material": (
        "Material Awareness",
        "Compare what is captured, what recaptures, and what remains attacked.",
        ("Count the exchange sequence.", "Recheck loose pieces after every capture."),
        "Winning a pawn while losing a more valuable piece.",
    ),
}


def generate_lessons(
    profile_id: str,
    weaknesses: tuple[WeaknessScore, ...],
    practice: tuple[PracticeItem, ...],
) -> tuple[Lesson, ...]:
    lessons = []
    for weakness in weaknesses:
        matching = tuple(item for item in practice if item.theme == weakness.theme)
        if not matching:
            continue
        template = LESSON_TEMPLATES.get(weakness.theme, LESSON_TEMPLATES["calculation"])
        example = matching[0]
        lessons.append(
            Lesson(
                str(uuid5(NAMESPACE_URL, f"lesson:{profile_id}:{weakness.theme}")),
                profile_id,
                weakness.theme,
                template[0],
                template[1],
                template[2],
                example.source_game_id,
                example.source_ply,
                template[3],
                tuple(item.id for item in matching),
            )
        )
    return tuple(lessons)
