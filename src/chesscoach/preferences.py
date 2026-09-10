"""Persistent, non-secret interface and analysis preferences."""

from dataclasses import dataclass

from PySide6.QtCore import QSettings

from chesscoach.coach.models import AnalysisProfile


@dataclass(frozen=True)
class UserPreferences:
    board_orientation: str = "player"
    board_theme: str = "classic"
    piece_scale: int = 100
    analysis_profile: str = "standard"
    review_perspective: str = "player"
    show_best_move: bool = True
    coach_verbosity: str = "detailed"
    text_scale: int = 100
    bot_move_delay_ms: int = 600
    profile_id: str = "default"

    @classmethod
    def load(cls, settings: QSettings) -> "UserPreferences":
        return cls(
            board_orientation=str(settings.value("display/orientation", "player")),
            board_theme=str(settings.value("display/board_theme", "classic")),
            piece_scale=int(str(settings.value("display/piece_scale", 100))),
            analysis_profile=str(settings.value("analysis/profile", "standard")),
            review_perspective=str(settings.value("review/perspective", "player")),
            show_best_move=str(settings.value("review/show_best_move", "true")).lower()
            in ("true", "1"),
            coach_verbosity=str(settings.value("coach/verbosity", "detailed")),
            text_scale=int(str(settings.value("display/text_scale", 100))),
            bot_move_delay_ms=int(str(settings.value("play/bot_move_delay_ms", 600))),
            profile_id=str(settings.value("learner/profile_id", "default")),
        )

    def save(self, settings: QSettings) -> None:
        settings.setValue("learner/profile_id", self.profile_id)
        settings.setValue("display/orientation", self.board_orientation)
        settings.setValue("display/board_theme", self.board_theme)
        settings.setValue("display/piece_scale", self.piece_scale)
        settings.setValue("analysis/profile", self.analysis_profile)
        settings.setValue("review/perspective", self.review_perspective)
        settings.setValue("review/show_best_move", self.show_best_move)
        settings.setValue("coach/verbosity", self.coach_verbosity)
        settings.setValue("display/text_scale", self.text_scale)
        settings.setValue("play/bot_move_delay_ms", self.bot_move_delay_ms)
        settings.sync()

    def engine_profile(self) -> AnalysisProfile:
        profiles = {
            "quick": AnalysisProfile("quick", 0.04, 0.16, 1, 8),
            "standard": AnalysisProfile(),
            "deep": AnalysisProfile("deep", 0.18, 0.8, 3, 12),
        }
        return profiles.get(self.analysis_profile, profiles["standard"])
