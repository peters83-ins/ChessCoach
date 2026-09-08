import json
from dataclasses import replace

import pytest

from chesscoach.coach.feedback import FeedbackError, LocalTemplateProvider, OpenAIProvider
from chesscoach.coach.models import (
    CoachingContext,
    EngineScore,
    Evidence,
    GamePhase,
    MoveAnalysis,
    MoveClassification,
)


def context() -> CoachingContext:
    move = MoveAnalysis(
        1,
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "white",
        "f2f3",
        "f3",
        "e2e4",
        "e4",
        EngineScore(centipawns=50),
        EngineScore(centipawns=-100),
        12,
        82,
        MoveClassification.MISTAKE,
        GamePhase.OPENING,
        ("e2e4", "e7e5"),
        ("f2f3", "e7e5"),
        12,
        (Evidence("fact-1", "opening_development", "The center was neglected."),),
        ("opening_development",),
    )
    return CoachingContext("game-1", move)


class FakeResponses:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return type("Response", (), {"output_text": json.dumps(self.output)})()


class FakeClient:
    def __init__(self, output: dict[str, object]) -> None:
        self.responses = FakeResponses(output)


def test_local_feedback_uses_supplied_evidence() -> None:
    feedback = LocalTemplateProvider().generate((context(),))[0]
    assert feedback.provider == "local"
    assert feedback.evidence_ids == ("fact-1",)
    assert "mistake" in feedback.explanation.lower()


def test_openai_feedback_sends_selected_context_and_validates_output() -> None:
    output = {
        "feedback": [
            {
                "ply": 1,
                "verdict": "Mistake",
                "explanation": "The move neglected the center.",
                "evidence_ids": ["fact-1"],
                "continuation": ["e2e4", "e7e5"],
                "takeaway": "Develop toward the center.",
                "confidence": 0.9,
            }
        ]
    }
    client = FakeClient(output)
    feedback = OpenAIProvider(client, "test-model").generate((context(),))[0]
    assert feedback.provider == "openai"
    sent = json.loads(str(client.responses.calls[0]["input"]))
    assert set(sent[0]) == {
        "game_id",
        "ply",
        "fen",
        "mover",
        "played",
        "best",
        "classification",
        "loss_percent",
        "best_pv",
        "played_pv",
        "evidence",
    }


def test_openai_feedback_rejects_unknown_evidence_and_illegal_lines() -> None:
    base = {
        "ply": 1,
        "verdict": "Mistake",
        "explanation": "Explanation",
        "evidence_ids": ["unknown"],
        "continuation": ["e2e4"],
        "takeaway": "Takeaway",
        "confidence": 1,
    }
    with pytest.raises(FeedbackError, match="unsupported"):
        OpenAIProvider(FakeClient({"feedback": [base]}), "model").generate((context(),))
    illegal = replace(context().move, evidence=context().move.evidence)
    assert illegal.fen == context().move.fen
    with pytest.raises(FeedbackError, match="illegal"):
        OpenAIProvider(
            FakeClient(
                {"feedback": [{**base, "evidence_ids": ["fact-1"], "continuation": ["e2e5"]}]}
            ),
            "model",
        ).generate((context(),))
    with pytest.raises(FeedbackError, match="not supplied"):
        OpenAIProvider(
            FakeClient(
                {
                    "feedback": [
                        {
                            **base,
                            "evidence_ids": ["fact-1"],
                            "continuation": ["g1f3"],
                        }
                    ]
                }
            ),
            "model",
        ).generate((context(),))
