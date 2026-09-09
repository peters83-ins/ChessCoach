"""Stable domain contracts for analysis and coaching."""

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum

import chess


class MoveClassification(StrEnum):
    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


class GamePhase(StrEnum):
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


@dataclass(frozen=True)
class AnalysisProfile:
    name: str = "standard"
    quick_time: float = 0.08
    deep_time: float = 0.35
    multipv: int = 2
    pv_plies: int = 10
    engine_signature: str = "stockfish"

    def validate(self) -> None:
        if not self.name or self.quick_time <= 0 or self.deep_time < self.quick_time:
            raise ValueError("Analysis times and profile name must be valid.")
        if self.multipv < 1 or self.pv_plies < 2:
            raise ValueError("Analysis requires MultiPV and at least two PV plies.")


@dataclass(frozen=True)
class EngineScore:
    centipawns: int | None = None
    mate: int | None = None

    def __post_init__(self) -> None:
        if (self.centipawns is None) == (self.mate is None):
            raise ValueError("An engine score must contain centipawns or mate, but not both.")


@dataclass(frozen=True)
class Evidence:
    id: str
    tag: str
    summary: str
    squares: tuple[str, ...] = ()


@dataclass(frozen=True)
class MoveAnalysis:
    ply: int
    fen: str
    mover: str
    played_uci: str
    played_san: str
    best_uci: str
    best_san: str
    best_score: EngineScore
    played_score: EngineScore
    loss_percent: float
    accuracy: float
    classification: MoveClassification
    phase: GamePhase
    best_pv: tuple[str, ...]
    played_pv: tuple[str, ...]
    depth: int
    evidence: tuple[Evidence, ...] = ()
    tags: tuple[str, ...] = ()
    deepened: bool = False
    alternative_moves: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhaseSummary:
    phase: GamePhase
    accuracy: float
    mistakes: int
    moves: int


@dataclass(frozen=True)
class GameAnalysis:
    game_id: str
    profile: AnalysisProfile
    moves: tuple[MoveAnalysis, ...]
    turning_points: tuple[int, ...]
    player_accuracy: float
    phase_summaries: tuple[PhaseSummary, ...]


@dataclass(frozen=True)
class CoachingContext:
    game_id: str
    move: MoveAnalysis

    def selected_payload(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "ply": self.move.ply,
            "fen": self.move.fen,
            "mover": self.move.mover,
            "played": self.move.played_uci,
            "best": self.move.best_uci,
            "classification": self.move.classification.value,
            "loss_percent": round(self.move.loss_percent, 2),
            "best_pv": self.move.best_pv[:8],
            "played_pv": self.move.played_pv[:8],
            "evidence": [
                {"id": fact.id, "tag": fact.tag, "summary": fact.summary}
                for fact in self.move.evidence
            ],
        }

    @property
    def context_hash(self) -> str:
        payload = json.dumps(self.selected_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class CoachFeedback:
    game_id: str
    ply: int
    verdict: str
    explanation: str
    evidence_ids: tuple[str, ...]
    continuation: tuple[str, ...]
    takeaway: str
    confidence: float
    provider: str
    prompt_version: str = "coach-v1"
    model: str = ""
    context_hash: str = ""


@dataclass(frozen=True)
class WeaknessEvent:
    profile_id: str
    game_id: str
    ply: int
    theme: str
    severity: float
    confidence: float
    outcome: str = "observed"
    observed_at: str = ""


@dataclass(frozen=True)
class WeaknessScore:
    theme: str
    score: float
    occurrences: int


@dataclass(frozen=True)
class WeaknessDetail:
    theme: str
    score: float
    occurrences: int
    confidence: float
    trend: str
    examples: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class PracticeItem:
    id: str
    profile_id: str
    source_game_id: str
    source_ply: int
    fen: str
    theme: str
    solution: tuple[str, ...]
    alternatives: tuple[str, ...] = ()
    due_at: str = ""
    interval_days: int = 1
    ease: float = 2.0

    def validate_attempt(self, move: chess.Move) -> bool:
        board = chess.Board(self.fen)
        return move in board.legal_moves and move.uci() in (self.solution[:1] + self.alternatives)


@dataclass(frozen=True)
class PracticeProgress:
    total: int
    due: int
    attempted: int
    successful: int


@dataclass(frozen=True)
class Lesson:
    id: str
    profile_id: str
    theme: str
    title: str
    concept: str
    recognition_cues: tuple[str, ...]
    example_game_id: str
    example_ply: int
    common_error: str
    exercise_ids: tuple[str, ...]
    completed: bool = False


@dataclass(frozen=True)
class GameReport:
    accuracy: float
    summary: str
    strongest_plies: tuple[int, ...]
    critical_plies: tuple[int, ...]
    recurring_themes: tuple[str, ...]
    phase_summaries: tuple[PhaseSummary, ...]


@dataclass(frozen=True)
class CoachBundle:
    analysis: GameAnalysis
    feedback: tuple[CoachFeedback, ...]
    weaknesses: tuple[WeaknessScore, ...]
    practice: tuple[PracticeItem, ...]
    lessons: tuple[Lesson, ...]
    report: GameReport


@dataclass
class AnalysisProgress:
    completed: int
    total: int
    stage: str
    cached: int = 0
    details: dict[str, object] = field(default_factory=dict)
