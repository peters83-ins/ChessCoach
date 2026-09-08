"""Grounded local and optional cloud feedback providers."""

import json
from collections.abc import Sequence
from typing import Any, Protocol

import chess

from chesscoach.coach.models import CoachFeedback, CoachingContext, MoveClassification

PROMPT_VERSION = "coach-v1"


class FeedbackError(ValueError):
    pass


class FeedbackProvider(Protocol):
    name: str
    model: str

    def generate(self, contexts: Sequence[CoachingContext]) -> tuple[CoachFeedback, ...]: ...


class _Response(Protocol):
    output_text: str


class _Responses(Protocol):
    def create(self, **kwargs: object) -> _Response: ...


class ResponsesClient(Protocol):
    responses: _Responses


class LocalTemplateProvider:
    name = "local"
    model = ""

    def generate(self, contexts: Sequence[CoachingContext]) -> tuple[CoachFeedback, ...]:
        return tuple(self._one(context) for context in contexts)

    def _one(self, context: CoachingContext) -> CoachFeedback:
        move = context.move
        primary = move.evidence[0]
        strong = move.classification in (
            MoveClassification.BEST,
            MoveClassification.EXCELLENT,
            MoveClassification.GOOD,
        )
        verdict = move.classification.value.title()
        if strong:
            explanation = f"This was {verdict.lower()}. {primary.summary}"
            takeaway = "Keep comparing forcing moves and improve your least active piece."
        else:
            explanation = f"This was a {verdict.lower()}. {primary.summary}"
            takeaway = f"Before moving, check {move.best_san} and the opponent's forcing replies."
        return CoachFeedback(
            context.game_id,
            move.ply,
            verdict,
            explanation,
            (primary.id,),
            move.best_pv[:6],
            takeaway,
            1.0,
            self.name,
            context_hash=context.context_hash,
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, client: ResponsesClient, model: str) -> None:
        if not model:
            raise ValueError("An OpenAI model is required.")
        self.client = client
        self.model = model

    def generate(self, contexts: Sequence[CoachingContext]) -> tuple[CoachFeedback, ...]:
        payloads = [context.selected_payload() for context in contexts]
        response = self.client.responses.create(
            model=self.model,
            instructions=(
                "Explain only the supplied Stockfish facts. Never invent moves, threats, "
                "or theory. "
                "Return JSON matching the schema. Keep each explanation under 80 words."
            ),
            input=json.dumps(payloads),
            text={"format": _response_format()},
            store=False,
            timeout=30.0,
        )
        try:
            items = json.loads(response.output_text)["feedback"]
        except (AttributeError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise FeedbackError("The AI response was not valid structured feedback.") from error
        by_ply = {context.move.ply: context for context in contexts}
        feedback = tuple(self._validate_item(item, by_ply) for item in items)
        if set(by_ply) != {item.ply for item in feedback}:
            raise FeedbackError("The AI response did not cover the requested moves.")
        return feedback

    def _validate_item(
        self, item: dict[str, Any], contexts: dict[int, CoachingContext]
    ) -> CoachFeedback:
        try:
            ply = int(item["ply"])
            context = contexts[ply]
            evidence_ids = tuple(str(value) for value in item["evidence_ids"])
            continuation = tuple(str(value) for value in item["continuation"])
            confidence = float(item["confidence"])
        except (KeyError, TypeError, ValueError) as error:
            raise FeedbackError("The AI feedback fields are invalid.") from error
        allowed = {fact.id for fact in context.move.evidence}
        if not evidence_ids or not set(evidence_ids).issubset(allowed):
            raise FeedbackError("The AI referenced unsupported evidence.")
        expected_verdict = context.move.classification.value
        if str(item["verdict"]).strip().lower() != expected_verdict:
            raise FeedbackError("The AI changed the engine-backed move classification.")
        board = chess.Board(context.move.fen)
        for uci in continuation:
            try:
                move = chess.Move.from_uci(uci)
            except ValueError as error:
                raise FeedbackError("The AI returned invalid move notation.") from error
            if move not in board.legal_moves:
                raise FeedbackError("The AI returned an illegal continuation.")
            board.push(move)
        supplied_lines = (context.move.best_pv, context.move.played_pv)
        if continuation and not any(
            continuation == line[: len(continuation)] for line in supplied_lines
        ):
            raise FeedbackError("The AI returned a continuation not supplied by Stockfish.")
        if not str(item["explanation"]).strip() or not str(item["takeaway"]).strip():
            raise FeedbackError("The AI returned empty coaching text.")
        return CoachFeedback(
            context.game_id,
            ply,
            str(item["verdict"]),
            str(item["explanation"]),
            evidence_ids,
            continuation,
            str(item["takeaway"]),
            max(0.0, min(confidence, 1.0)),
            "openai",
            PROMPT_VERSION,
            self.model,
            context.context_hash,
        )


def _response_format() -> dict[str, object]:
    item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ply": {"type": "integer"},
            "verdict": {"type": "string"},
            "explanation": {"type": "string"},
            "evidence_ids": {"type": "array", "items": {"type": "string"}},
            "continuation": {"type": "array", "items": {"type": "string"}},
            "takeaway": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "ply",
            "verdict",
            "explanation",
            "evidence_ids",
            "continuation",
            "takeaway",
            "confidence",
        ],
    }
    return {
        "type": "json_schema",
        "name": "chess_coach_feedback",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"feedback": {"type": "array", "items": item}},
            "required": ["feedback"],
        },
    }
