"""Immutable contracts for locally reviewed course content and progress."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CourseExercise:
    id: str
    module_id: str
    fen: str
    learner_color: str
    line: tuple[str, ...]
    alternatives: tuple[tuple[str, ...], ...] = ()
    prompt: str = ""
    hints: tuple[str, ...] = ()
    explanation: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CourseModule:
    id: str
    title: str
    summary: str
    exercise_ids: tuple[str, ...]
    order: int = 0


@dataclass(frozen=True)
class Course:
    id: str
    version: int
    title: str
    description: str
    level_min: int
    level_max: int
    side: str
    estimated_minutes: int
    modules: tuple[CourseModule, ...]
    exercises: tuple[CourseExercise, ...]

    def exercise(self, exercise_id: str) -> CourseExercise:
        for exercise in self.exercises:
            if exercise.id == exercise_id:
                return exercise
        raise KeyError(exercise_id)


@dataclass(frozen=True)
class MoveMastery:
    profile_id: str
    course_id: str
    exercise_id: str
    decision_index: int
    level: int = 0
    due_at: str = ""
    attempts: int = 0
    errors: int = 0
    hints: int = 0
    last_result: str = ""
