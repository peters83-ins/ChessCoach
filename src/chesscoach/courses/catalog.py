"""Load and validate offline course JSON without database access."""

import json
from pathlib import Path
from typing import Any

import chess

from chesscoach.courses.models import Course, CourseExercise, CourseModule


class CourseCatalogError(ValueError):
    """Raised when course content is malformed or contains an illegal line."""


class CourseCatalog:
    SCHEMA_VERSION = 1

    def __init__(self, courses: tuple[Course, ...] = ()) -> None:
        self.courses = courses

    @classmethod
    def from_file(cls, path: Path) -> "CourseCatalog":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CourseCatalogError(f"Could not read course content: {exc}") from exc
        return cls.from_data(payload)

    @classmethod
    def from_directory(cls, path: Path) -> "CourseCatalog":
        """Load and combine reviewed JSON course packs from a directory."""
        if not path.is_dir():
            raise CourseCatalogError(f"Course directory does not exist: {path}")
        files = tuple(sorted(path.glob("*.json")))
        if not files:
            raise CourseCatalogError(f"Course directory is empty: {path}")
        courses: list[Course] = []
        for file in files:
            courses.extend(cls.from_file(file).courses)
        ids = [course.id for course in courses]
        if len(ids) != len(set(ids)):
            raise CourseCatalogError("Course IDs must be unique across content packs.")
        return cls(tuple(courses))

    @classmethod
    def from_data(cls, payload: Any) -> "CourseCatalog":
        if not isinstance(payload, dict) or payload.get("schema_version") != cls.SCHEMA_VERSION:
            raise CourseCatalogError("Unsupported course schema version.")
        raw_courses = payload.get("courses")
        if not isinstance(raw_courses, list):
            raise CourseCatalogError("Course catalog must contain a courses list.")
        courses = tuple(cls._course(item) for item in raw_courses)
        ids = [course.id for course in courses]
        if len(ids) != len(set(ids)):
            raise CourseCatalogError("Course IDs must be unique.")
        return cls(courses)

    @classmethod
    def built_in(cls) -> "CourseCatalog":
        path = Path(__file__).parent / "content" / "courses.json"
        return cls.from_file(path) if path.is_file() else cls()

    @classmethod
    def _course(cls, raw: Any) -> Course:
        if not isinstance(raw, dict):
            raise CourseCatalogError("Each course must be an object.")
        try:
            modules = tuple(cls._module(item) for item in raw["modules"])
            exercises = tuple(cls._exercise(item) for item in raw["exercises"])
            course = Course(
                id=str(raw["id"]),
                version=int(raw["version"]),
                title=str(raw["title"]),
                description=str(raw.get("description", "")),
                level_min=int(raw["level_min"]),
                level_max=int(raw["level_max"]),
                side=str(raw["side"]).lower(),
                estimated_minutes=int(raw.get("estimated_minutes", 0)),
                modules=modules,
                exercises=exercises,
                attribution=str(raw.get("attribution", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CourseCatalogError(f"Invalid course fields: {exc}") from exc
        cls.validate(course)
        return course

    @staticmethod
    def _module(raw: Any) -> CourseModule:
        if not isinstance(raw, dict):
            raise CourseCatalogError("Each module must be an object.")
        return CourseModule(
            id=str(raw["id"]),
            title=str(raw["title"]),
            summary=str(raw.get("summary", "")),
            exercise_ids=tuple(str(item) for item in raw.get("exercise_ids", ())),
            order=int(raw.get("order", 0)),
        )

    @staticmethod
    def _exercise(raw: Any) -> CourseExercise:
        if not isinstance(raw, dict):
            raise CourseCatalogError("Each exercise must be an object.")
        return CourseExercise(
            id=str(raw["id"]),
            module_id=str(raw["module_id"]),
            fen=str(raw["fen"]),
            learner_color=str(raw["learner_color"]).lower(),
            line=tuple(str(move) for move in raw["line"]),
            alternatives=tuple(
                tuple(str(move) for move in line) for line in raw.get("alternatives", ())
            ),
            prompt=str(raw.get("prompt", "")),
            hints=tuple(str(item) for item in raw.get("hints", ())),
            explanation=str(raw.get("explanation", "")),
            tags=tuple(str(item) for item in raw.get("tags", ())),
        )

    @classmethod
    def validate(cls, course: Course) -> None:
        if course.version < 1 or course.level_min < 0 or course.level_max < course.level_min:
            raise CourseCatalogError(f"Invalid metadata for course {course.id}.")
        if course.side not in {"white", "black", "both"}:
            raise CourseCatalogError(f"Invalid course side for {course.id}.")
        module_ids = {module.id for module in course.modules}
        exercise_ids = {exercise.id for exercise in course.exercises}
        if len(module_ids) != len(course.modules) or len(exercise_ids) != len(course.exercises):
            raise CourseCatalogError(f"IDs must be unique in course {course.id}.")
        listed: set[str] = set()
        for module in course.modules:
            for exercise_id in module.exercise_ids:
                if exercise_id not in exercise_ids or exercise_id in listed:
                    raise CourseCatalogError(f"Invalid module exercise reference: {exercise_id}.")
                listed.add(exercise_id)
        if listed != exercise_ids:
            raise CourseCatalogError(f"Every exercise must belong to one module in {course.id}.")
        for exercise in course.exercises:
            if exercise.module_id not in module_ids:
                raise CourseCatalogError(f"Unknown module for exercise {exercise.id}.")
            if exercise.learner_color not in {"white", "black"}:
                raise CourseCatalogError(f"Invalid learner color for {exercise.id}.")
            cls._validate_line(exercise)

    @staticmethod
    def _validate_line(exercise: CourseExercise) -> None:
        try:
            board = chess.Board(exercise.fen)
        except ValueError as exc:
            raise CourseCatalogError(f"Invalid FEN for {exercise.id}.") from exc
        learner = chess.WHITE if exercise.learner_color == "white" else chess.BLACK
        for line in (exercise.line, *exercise.alternatives):
            if not line:
                raise CourseCatalogError(f"Exercise {exercise.id} has an empty line.")
            current = board.copy()
            decisions = 0
            for uci in line:
                try:
                    move = chess.Move.from_uci(uci)
                except ValueError as exc:
                    raise CourseCatalogError(f"Invalid move {uci} in {exercise.id}.") from exc
                if move not in current.legal_moves:
                    raise CourseCatalogError(f"Illegal move {uci} in {exercise.id}.")
                if current.turn == learner:
                    decisions += 1
                current.push(move)
            if decisions > 2:
                raise CourseCatalogError(f"Exercise {exercise.id} exceeds two learner decisions.")

    def search(
        self, query: str = "", side: str = "all", level: int | None = None
    ) -> tuple[Course, ...]:
        needle = query.strip().lower()
        selected_side = side.lower()
        return tuple(
            course
            for course in self.courses
            if (not needle or needle in f"{course.title} {course.description} {course.id}".lower())
            and (selected_side in {"all", course.side, "both"} or course.side == "both")
            and (level is None or course.level_min <= level <= course.level_max)
        )
