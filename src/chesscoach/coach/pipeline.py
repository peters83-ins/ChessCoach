"""Compose feedback, weakness, practice, lesson, and report outputs."""

from collections.abc import Sequence

from chesscoach.coach.feedback import FeedbackProvider, LocalTemplateProvider
from chesscoach.coach.lessons import generate_lessons
from chesscoach.coach.models import (
    CoachBundle,
    CoachFeedback,
    CoachingContext,
    GameAnalysis,
    MoveClassification,
)
from chesscoach.coach.practice import generate_practice_items
from chesscoach.coach.report import build_report
from chesscoach.coach.weakness import aggregate_weaknesses, weakness_events
from chesscoach.storage.coach import DEFAULT_PROFILE_ID, CoachRepository
from chesscoach.storage.database import GameData


class CoachPipeline:
    def __init__(self, repository: CoachRepository | None = None) -> None:
        self.repository = repository

    def build(
        self,
        data: GameData,
        analysis: GameAnalysis,
        cloud_provider: FeedbackProvider | None = None,
    ) -> CoachBundle:
        contexts = tuple(CoachingContext(data.id, move) for move in analysis.moves)
        local = LocalTemplateProvider().generate(contexts)
        stored = self.repository.load_feedback(data.id) if self.repository else ()
        feedback = self._cloud_enrichment(
            contexts, local, cloud_provider, data.player_color, stored
        )
        events = weakness_events(DEFAULT_PROFILE_ID, data.id, analysis.moves, data.player_color)
        current_practice = generate_practice_items(
            DEFAULT_PROFILE_ID, data.id, analysis.moves, data.player_color
        )
        if self.repository:
            self.repository.save_feedback(feedback)
            self.repository.save_learning(events, current_practice, ())
            weaknesses = self.repository.weakness_scores()
            practice = self.repository.practice_items()
        else:
            weaknesses = aggregate_weaknesses(events)
            practice = current_practice
        lessons = generate_lessons(DEFAULT_PROFILE_ID, weaknesses, practice)
        if self.repository:
            self.repository.save_learning((), (), lessons)
        return CoachBundle(
            analysis,
            feedback,
            weaknesses,
            practice,
            lessons,
            build_report(analysis, data.player_color, weaknesses),
        )

    def load(self, data: GameData) -> CoachBundle | None:
        if self.repository is None:
            return None
        analysis = self.repository.load_latest_analysis(data.id)
        if analysis is None:
            return None
        weaknesses = self.repository.weakness_scores()
        practice = self.repository.practice_items()
        lessons = self.repository.lessons()
        contexts = tuple(CoachingContext(data.id, move) for move in analysis.moves)
        stored = self.repository.load_feedback(data.id)
        feedback = []
        for context in contexts:
            matches = [
                item
                for item in stored
                if item.ply == context.move.ply and item.context_hash == context.context_hash
            ]
            if matches:
                feedback.append(max(matches, key=lambda item: item.provider == "openai"))
        return CoachBundle(
            analysis,
            tuple(feedback),
            weaknesses,
            practice,
            lessons,
            build_report(analysis, data.player_color, weaknesses),
        )

    @staticmethod
    def _cloud_enrichment(
        contexts: tuple[CoachingContext, ...],
        local: tuple[CoachFeedback, ...],
        provider: FeedbackProvider | None,
        player_color: str,
        stored: tuple[CoachFeedback, ...],
    ) -> tuple[CoachFeedback, ...]:
        if provider is None:
            return local
        current_hashes = {context.move.ply: context.context_hash for context in contexts}
        valid_cache = {
            (item.ply, item.context_hash): item
            for item in stored
            if item.provider == provider.name
            and item.model == provider.model
            and current_hashes.get(item.ply) == item.context_hash
        }
        selected = tuple(
            context
            for context in contexts
            if context.move.mover == player_color
            and context.move.classification
            in (
                MoveClassification.INACCURACY,
                MoveClassification.MISTAKE,
                MoveClassification.BLUNDER,
            )
            and (context.move.ply, context.context_hash) not in valid_cache
        )
        enriched: dict[int, CoachFeedback] = {item.ply: item for item in local}
        enriched.update((ply, item) for (ply, _), item in valid_cache.items())
        for batch in _batches(selected, 4):
            try:
                enriched.update((item.ply, item) for item in provider.generate(batch))
            except Exception:
                continue
        return tuple(enriched[context.move.ply] for context in contexts)


def _batches(
    contexts: Sequence[CoachingContext], size: int
) -> tuple[tuple[CoachingContext, ...], ...]:
    return tuple(tuple(contexts[index : index + size]) for index in range(0, len(contexts), size))
