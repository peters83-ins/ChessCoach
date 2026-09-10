"""Versioned SQLite storage for analysis, coaching, practice, and lessons."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import chess

from chesscoach.coach.adaptive import next_course_due
from chesscoach.coach.models import (
    AnalysisProfile,
    CoachFeedback,
    EngineScore,
    Evidence,
    GameAnalysis,
    GamePhase,
    Lesson,
    MoveAnalysis,
    MoveClassification,
    PracticeItem,
    PracticeProgress,
    WeaknessDetail,
    WeaknessEvent,
    WeaknessScore,
)
from chesscoach.coach.practice import schedule_attempt
from chesscoach.courses.models import Course, MoveMastery

SCHEMA_VERSION = 5
DEFAULT_PROFILE_ID = "default"


@dataclass(frozen=True)
class AnalysisRunStatus:
    state: str
    completed: int
    total: int
    error: str = ""


@dataclass(frozen=True)
class GameLearningStatus:
    analyzed: bool
    practice_count: int


@dataclass(frozen=True)
class CourseProgress:
    profile_id: str
    course_id: str
    content_version: int
    last_module_id: str
    completed: bool
    updated_at: str


@dataclass(frozen=True)
class PlayerProfile:
    profile_id: str
    name: str
    created_at: str


@dataclass(frozen=True)
class CachedProfileSummary:
    profile: str
    runs: int


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def _move_from_dict(data: dict[str, Any]) -> MoveAnalysis:
    return MoveAnalysis(
        ply=int(data["ply"]),
        fen=str(data["fen"]),
        mover=str(data["mover"]),
        played_uci=str(data["played_uci"]),
        played_san=str(data["played_san"]),
        best_uci=str(data["best_uci"]),
        best_san=str(data["best_san"]),
        best_score=EngineScore(**data["best_score"]),
        played_score=EngineScore(**data["played_score"]),
        loss_percent=float(data["loss_percent"]),
        accuracy=float(data["accuracy"]),
        classification=MoveClassification(str(data["classification"])),
        phase=GamePhase(str(data["phase"])),
        best_pv=tuple(str(move) for move in data["best_pv"]),
        played_pv=tuple(str(move) for move in data["played_pv"]),
        depth=int(data["depth"]),
        evidence=tuple(
            Evidence(
                id=str(fact["id"]),
                tag=str(fact["tag"]),
                summary=str(fact["summary"]),
                squares=tuple(fact["squares"]),
            )
            for fact in data["evidence"]
        ),
        tags=tuple(str(tag) for tag in data["tags"]),
        deepened=bool(data["deepened"]),
        alternative_moves=tuple(str(move) for move in data.get("alternative_moves", ())),
    )


class CoachRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._schema_ready = False

    def _connect(self) -> sqlite3.Connection:
        """Open a consistently configured repository connection."""
        connection = sqlite3.connect(self.path, timeout=3.0)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def migrate(self) -> None:
        # A repository instance owns one database path. Avoid reopening and
        # rechecking the schema on every read/write in a review session.
        if self._schema_ready and self.path.is_file():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_versions ("
                "component TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            row = connection.execute(
                "SELECT version FROM schema_versions WHERE component='coach'"
            ).fetchone()
            version = int(row[0]) if row else self._detect_schema_version(connection)
            if version > SCHEMA_VERSION:
                raise ValueError("The coaching database schema is newer than this application.")
            if version < 1:
                self._migration_one(connection)
            elif version < 2:
                self._migration_one(connection)
                self._migration_two(connection)
            if version < 3:
                self._migration_three(connection)
            if version < 4:
                self._migration_four(connection)
            if version < 5:
                self._migration_five(connection)
            if version < SCHEMA_VERSION:
                connection.execute(
                    "INSERT INTO schema_versions VALUES ('coach', ?) "
                    "ON CONFLICT(component) DO UPDATE SET version=excluded.version",
                    (SCHEMA_VERSION,),
                )
            self._schema_ready = True

    def profiles(self) -> tuple[PlayerProfile, ...]:
        self.migrate()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT id, name, created_at FROM player_profiles ORDER BY created_at, id"
            ).fetchall()
        return tuple(PlayerProfile(str(row[0]), str(row[1]), str(row[2])) for row in rows)

    def create_profile(self, name: str, profile_id: str | None = None) -> PlayerProfile:
        """Create a stable profile identifier without copying another profile's data."""
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("Profile name cannot be empty.")
        identifier = profile_id or str(uuid4())
        if not identifier.strip() or identifier == DEFAULT_PROFILE_ID:
            raise ValueError("Profile identifier is reserved or empty.")
        profile = PlayerProfile(identifier, clean_name, _now())
        self.migrate()
        with closing(self._connect()) as connection, connection:
            try:
                connection.execute(
                    "INSERT INTO player_profiles(id, name, created_at) VALUES (?, ?, ?)",
                    (profile.profile_id, profile.name, profile.created_at),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Profile identifier already exists.") from error
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a non-default profile and its learning records atomically."""
        if profile_id == DEFAULT_PROFILE_ID:
            raise ValueError("The default profile cannot be deleted.")
        self.migrate()
        with closing(self._connect()) as connection, connection:
            exists = connection.execute(
                "SELECT 1 FROM player_profiles WHERE id=?", (profile_id,)
            ).fetchone()
            if exists is None:
                return False
            for table in (
                "weakness_events",
                "dismissed_weaknesses",
                "practice_items",
                "practice_attempts",
                "lessons",
                "lesson_progress",
                "course_progress",
                "course_mastery",
                "course_attempts",
            ):
                column = "profile_id"
                if table == "lesson_progress":
                    continue
                if table == "practice_attempts":
                    connection.execute(
                        "DELETE FROM practice_attempts WHERE item_id IN "
                        "(SELECT id FROM practice_items WHERE profile_id=?)",
                        (profile_id,),
                    )
                    continue
                connection.execute(f"DELETE FROM {table} WHERE {column}=?", (profile_id,))
            connection.execute("DELETE FROM player_profiles WHERE id=?", (profile_id,))
        return True

    @staticmethod
    def _detect_schema_version(connection: sqlite3.Connection) -> int:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='coach_feedback'"
        ).fetchone()
        if exists is None:
            return 0
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(coach_feedback)")}
        return 2 if {"model", "context_hash"}.issubset(columns) else 1

    @staticmethod
    def _migration_one(connection: sqlite3.Connection) -> None:
        statements = (
            "CREATE TABLE IF NOT EXISTS analysis_runs ("
            "id TEXT PRIMARY KEY, game_id TEXT NOT NULL, profile_json TEXT NOT NULL, "
            "engine_signature TEXT NOT NULL, state TEXT NOT NULL, completed INTEGER NOT NULL, "
            "total INTEGER NOT NULL, error TEXT, created_at TEXT NOT NULL, "
            "updated_at TEXT NOT NULL)",
            "CREATE INDEX IF NOT EXISTS analysis_runs_game ON analysis_runs(game_id, updated_at)",
            "CREATE TABLE IF NOT EXISTS analysis_cache ("
            "cache_key TEXT PRIMARY KEY, data_json TEXT NOT NULL, updated_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS move_analyses ("
            "run_id TEXT NOT NULL, ply INTEGER NOT NULL, data_json TEXT NOT NULL, "
            "PRIMARY KEY(run_id, ply), FOREIGN KEY(run_id) REFERENCES analysis_runs(id) "
            "ON DELETE CASCADE)",
            "CREATE TABLE IF NOT EXISTS coach_feedback ("
            "game_id TEXT NOT NULL, ply INTEGER NOT NULL, provider TEXT NOT NULL, "
            "prompt_version TEXT NOT NULL, model TEXT NOT NULL, context_hash TEXT NOT NULL, "
            "data_json TEXT NOT NULL, created_at TEXT NOT NULL, "
            "PRIMARY KEY(game_id, ply, provider, prompt_version, model, context_hash))",
            "CREATE TABLE IF NOT EXISTS player_profiles ("
            "id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS weakness_events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id TEXT NOT NULL, "
            "game_id TEXT NOT NULL, ply INTEGER NOT NULL, theme TEXT NOT NULL, "
            "severity REAL NOT NULL, confidence REAL NOT NULL, "
            "outcome TEXT NOT NULL, created_at TEXT NOT NULL, "
            "UNIQUE(profile_id, game_id, ply, theme, outcome))",
            "CREATE TABLE IF NOT EXISTS practice_items ("
            "id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, source_game_id TEXT NOT NULL, "
            "source_ply INTEGER NOT NULL, theme TEXT NOT NULL, due_at TEXT NOT NULL, "
            "data_json TEXT NOT NULL)",
            "CREATE INDEX IF NOT EXISTS practice_due ON practice_items(profile_id, due_at)",
            "CREATE TABLE IF NOT EXISTS practice_attempts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL, "
            "attempted_at TEXT NOT NULL, "
            "move_uci TEXT NOT NULL, successful INTEGER NOT NULL)",
            "CREATE TABLE IF NOT EXISTS lessons ("
            "id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, theme TEXT NOT NULL, "
            "data_json TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS lesson_progress ("
            "lesson_id TEXT PRIMARY KEY, completed INTEGER NOT NULL, updated_at TEXT NOT NULL)",
        )
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in statements:
            connection.execute(statement)
        connection.execute(
            "INSERT OR IGNORE INTO player_profiles VALUES (?, ?, ?)",
            (DEFAULT_PROFILE_ID, "Local player", _now()),
        )

    @staticmethod
    def _migration_two(connection: sqlite3.Connection) -> None:
        connection.execute("ALTER TABLE coach_feedback RENAME TO coach_feedback_v1")
        connection.execute(
            "CREATE TABLE coach_feedback (game_id TEXT NOT NULL, ply INTEGER NOT NULL, "
            "provider TEXT NOT NULL, prompt_version TEXT NOT NULL, model TEXT NOT NULL, "
            "context_hash TEXT NOT NULL, data_json TEXT NOT NULL, created_at TEXT NOT NULL, "
            "PRIMARY KEY(game_id, ply, provider, prompt_version, model, context_hash))"
        )
        connection.execute(
            "INSERT INTO coach_feedback SELECT game_id, ply, provider, prompt_version, '', '', "
            "data_json, created_at FROM coach_feedback_v1"
        )
        connection.execute("DROP TABLE coach_feedback_v1")

    @staticmethod
    def _migration_three(connection: sqlite3.Connection) -> None:
        lesson_columns = {
            str(row[1]) for row in connection.execute("PRAGMA table_info(lesson_progress)")
        }
        if lesson_columns and "step" not in lesson_columns:
            connection.execute(
                "ALTER TABLE lesson_progress ADD COLUMN step INTEGER NOT NULL DEFAULT 0"
            )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS dismissed_weaknesses ("
            "profile_id TEXT NOT NULL, theme TEXT NOT NULL, dismissed_at TEXT NOT NULL, "
            "PRIMARY KEY(profile_id, theme))"
        )

    @staticmethod
    def _migration_four(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS course_progress ("
            "profile_id TEXT NOT NULL, course_id TEXT NOT NULL, content_version INTEGER NOT NULL, "
            "last_module_id TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0, "
            "enrolled_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
            "PRIMARY KEY(profile_id, course_id))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS course_mastery ("
            "profile_id TEXT NOT NULL, course_id TEXT NOT NULL, exercise_id TEXT NOT NULL, "
            "decision_index INTEGER NOT NULL, level INTEGER NOT NULL DEFAULT 0, "
            "due_at TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, "
            "errors INTEGER NOT NULL DEFAULT 0, hints INTEGER NOT NULL DEFAULT 0, "
            "last_result TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL, "
            "PRIMARY KEY(profile_id, course_id, exercise_id, decision_index))"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS course_attempts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id TEXT NOT NULL, "
            "course_id TEXT NOT NULL, exercise_id TEXT NOT NULL, decision_index INTEGER NOT NULL, "
            "attempted_at TEXT NOT NULL, "
            "move_uci TEXT NOT NULL, correct INTEGER NOT NULL, hints INTEGER NOT NULL DEFAULT 0)"
        )

    @staticmethod
    def _migration_five(connection: sqlite3.Connection) -> None:
        """Add indexes for the review and due-learning query paths."""
        for statement in (
            "CREATE INDEX IF NOT EXISTS weakness_events_profile_theme "
            "ON weakness_events(profile_id, theme, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS course_mastery_due "
            "ON course_mastery(profile_id, due_at, course_id, exercise_id)",
            "CREATE INDEX IF NOT EXISTS course_attempts_profile_time "
            "ON course_attempts(profile_id, attempted_at DESC)",
        ):
            connection.execute(statement)

    def start_run(self, game_id: str, profile: AnalysisProfile) -> str:
        self.migrate()
        run_id = str(uuid4())
        now = _now()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO analysis_runs VALUES (?, ?, ?, ?, 'running', 0, 0, NULL, ?, ?)",
                (run_id, game_id, _json(asdict(profile)), profile.engine_signature, now, now),
            )
        return run_id

    def update_run(
        self,
        run_id: str,
        state: str,
        completed: int,
        total: int,
        error: str | None = None,
    ) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE analysis_runs SET state=?, completed=?, total=?, error=?, "
                "updated_at=? WHERE id=?",
                (state, completed, total, error, _now(), run_id),
            )

    def latest_run_status(self, game_id: str) -> AnalysisRunStatus | None:
        """Return the latest job state so interrupted work can be explained and resumed."""
        if not self.path.is_file():
            return None
        self.migrate()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT state, completed, total, COALESCE(error, '') FROM analysis_runs "
                "WHERE game_id=? ORDER BY updated_at DESC LIMIT 1",
                (game_id,),
            ).fetchone()
        return (
            AnalysisRunStatus(str(row[0]), int(row[1]), int(row[2]), str(row[3])) if row else None
        )

    def cached_profile_summaries(
        self, game_id: str | None = None
    ) -> tuple[CachedProfileSummary, ...]:
        """Return completed cached analysis profile counts for comparison views."""
        if not self.path.is_file():
            return ()
        self.migrate()
        query = "SELECT profile_json FROM analysis_runs WHERE state='complete'"
        parameters: tuple[str, ...] = ()
        if game_id is not None:
            query += " AND game_id=?"
            parameters = (game_id,)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()
        counts: dict[str, int] = {}
        for row in rows:
            try:
                profile = str(json.loads(str(row[0])).get("name", "standard"))
            except (TypeError, json.JSONDecodeError):
                profile = "standard"
            counts[profile] = counts.get(profile, 0) + 1
        return tuple(CachedProfileSummary(name, counts[name]) for name in sorted(counts))

    def game_learning_statuses(self, game_ids: tuple[str, ...]) -> dict[str, GameLearningStatus]:
        """Return library badges without loading full analyses or practice records."""
        if not game_ids or not self.path.is_file():
            return {}
        self.migrate()
        placeholders = ",".join("?" for _ in game_ids)
        with closing(self._connect()) as connection:
            analyzed = {
                str(row[0])
                for row in connection.execute(
                    f"SELECT DISTINCT game_id FROM analysis_runs WHERE state='complete' "
                    f"AND game_id IN ({placeholders})",
                    game_ids,
                )
            }
            practice = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    f"SELECT source_game_id, COUNT(*) FROM practice_items "
                    f"WHERE source_game_id IN ({placeholders}) GROUP BY source_game_id",
                    game_ids,
                )
            }
        return {
            game_id: GameLearningStatus(game_id in analyzed, practice.get(game_id, 0))
            for game_id in game_ids
        }

    def delete_game_learning(self, game_id: str) -> None:
        """Remove analysis and learning records that belong only to a deleted game."""
        if not self.path.is_file():
            return
        self.migrate()
        with closing(self._connect()) as connection, connection:
            practice_ids = tuple(
                str(row[0])
                for row in connection.execute(
                    "SELECT id FROM practice_items WHERE source_game_id=?", (game_id,)
                )
            )
            if practice_ids:
                placeholders = ",".join("?" for _ in practice_ids)
                connection.execute(
                    f"DELETE FROM practice_attempts WHERE item_id IN ({placeholders})",
                    practice_ids,
                )
            connection.execute("DELETE FROM practice_items WHERE source_game_id=?", (game_id,))
            connection.execute("DELETE FROM weakness_events WHERE game_id=?", (game_id,))
            connection.execute("DELETE FROM coach_feedback WHERE game_id=?", (game_id,))
            run_ids = tuple(
                str(row[0])
                for row in connection.execute(
                    "SELECT id FROM analysis_runs WHERE game_id=?", (game_id,)
                )
            )
            if run_ids:
                placeholders = ",".join("?" for _ in run_ids)
                connection.execute(
                    f"DELETE FROM move_analyses WHERE run_id IN ({placeholders})", run_ids
                )
            connection.execute("DELETE FROM analysis_runs WHERE game_id=?", (game_id,))

    def save_analysis(self, run_id: str, analysis: GameAnalysis) -> None:
        with closing(self._connect()) as connection, connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("DELETE FROM move_analyses WHERE run_id=?", (run_id,))
            connection.executemany(
                "INSERT INTO move_analyses VALUES (?, ?, ?)",
                ((run_id, move.ply, _json(asdict(move))) for move in analysis.moves),
            )
            connection.execute(
                "UPDATE analysis_runs SET profile_json=?, engine_signature=?, state='complete', "
                "completed=?, total=?, error=NULL, updated_at=? WHERE id=?",
                (
                    _json(asdict(analysis.profile)),
                    analysis.profile.engine_signature,
                    len(analysis.moves),
                    len(analysis.moves),
                    _now(),
                    run_id,
                ),
            )

    def load_latest_analysis(self, game_id: str) -> GameAnalysis | None:
        if not self.path.is_file():
            return None
        self.migrate()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT id, profile_json FROM analysis_runs WHERE game_id=? AND state='complete' "
                "ORDER BY updated_at DESC LIMIT 1",
                (game_id,),
            ).fetchone()
            if row is None:
                return None
            move_rows = connection.execute(
                "SELECT data_json FROM move_analyses WHERE run_id=? ORDER BY ply", (row[0],)
            ).fetchall()
        profile = AnalysisProfile(**json.loads(row[1]))
        moves = tuple(_move_from_dict(json.loads(item[0])) for item in move_rows)
        from chesscoach.coach.scoring import phase_summaries, player_accuracy, turning_points

        player_color = self._game_player_color(game_id)
        return GameAnalysis(
            game_id,
            profile,
            moves,
            turning_points(moves),
            player_accuracy(moves, player_color),
            phase_summaries(moves, player_color),
        )

    def _game_player_color(self, game_id: str) -> str:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT player_color FROM games WHERE id=?", (game_id,)
            ).fetchone()
        return str(row[0]) if row else "white"

    def stored_move_analyses(self, game_id: str | None = None) -> tuple[MoveAnalysis, ...]:
        """Return persisted move analyses for local charts without rerunning Stockfish."""
        if not self.path.is_file():
            return ()
        self.migrate()
        query = (
            "SELECT ma.data_json FROM move_analyses ma JOIN analysis_runs ar ON ar.id=ma.run_id "
            "WHERE ar.state='complete'"
        )
        params: tuple[object, ...] = ()
        if game_id is not None:
            query += " AND ar.game_id=?"
            params = (game_id,)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(_move_from_dict(json.loads(row[0])) for row in rows)

    def stored_move_analyses_by_game(self) -> tuple[tuple[str, MoveAnalysis], ...]:
        """Return complete persisted analyses with their source game IDs."""
        if not self.path.is_file():
            return ()
        self.migrate()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT ar.game_id, ma.data_json FROM move_analyses ma "
                "JOIN analysis_runs ar ON ar.id=ma.run_id WHERE ar.state='complete'"
            ).fetchall()
        return tuple((str(game_id), _move_from_dict(json.loads(data))) for game_id, data in rows)

    def get_move_analysis(self, key: str) -> MoveAnalysis | None:
        if not self.path.is_file():
            return None
        with closing(self._connect()) as connection:
            try:
                row = connection.execute(
                    "SELECT data_json FROM analysis_cache WHERE cache_key=?", (key,)
                ).fetchone()
            except sqlite3.OperationalError:
                return None
        return _move_from_dict(json.loads(row[0])) if row else None

    def put_move_analysis(self, key: str, analysis: MoveAnalysis) -> None:
        self.migrate()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO analysis_cache VALUES (?, ?, ?) ON CONFLICT(cache_key) DO UPDATE SET "
                "data_json=excluded.data_json, updated_at=excluded.updated_at",
                (key, _json(asdict(analysis)), _now()),
            )

    def save_feedback(self, feedback: tuple[CoachFeedback, ...]) -> None:
        if not feedback:
            return
        self.migrate()
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                "INSERT INTO coach_feedback VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT DO UPDATE SET "
                "data_json=excluded.data_json, created_at=excluded.created_at",
                (
                    (
                        item.game_id,
                        item.ply,
                        item.provider,
                        item.prompt_version,
                        item.model,
                        item.context_hash,
                        _json(asdict(item)),
                        _now(),
                    )
                    for item in feedback
                ),
            )

    def load_feedback(self, game_id: str) -> tuple[CoachFeedback, ...]:
        if not self.path.is_file():
            return ()
        with closing(self._connect()) as connection:
            try:
                rows = connection.execute(
                    "SELECT data_json FROM coach_feedback WHERE game_id=? ORDER BY ply", (game_id,)
                ).fetchall()
            except sqlite3.OperationalError:
                return ()
        return tuple(
            CoachFeedback(
                **{
                    **data,
                    "evidence_ids": tuple(data["evidence_ids"]),
                    "continuation": tuple(data["continuation"]),
                }
            )
            for data in (json.loads(row[0]) for row in rows)
        )

    def save_learning(
        self,
        events: tuple[WeaknessEvent, ...],
        practice: tuple[PracticeItem, ...],
        lessons: tuple[Lesson, ...],
    ) -> None:
        self.migrate()
        with closing(self._connect()) as connection, connection:
            connection.executemany(
                "INSERT INTO weakness_events(profile_id, game_id, ply, theme, severity, "
                "confidence, "
                "outcome, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(profile_id, game_id, ply, theme, outcome) DO UPDATE SET "
                "severity=excluded.severity, confidence=excluded.confidence",
                (
                    (
                        event.profile_id,
                        event.game_id,
                        event.ply,
                        event.theme,
                        event.severity,
                        event.confidence,
                        event.outcome,
                        event.observed_at or _now(),
                    )
                    for event in events
                ),
            )
            connection.executemany(
                "INSERT INTO practice_items VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO NOTHING",
                (
                    (
                        item.id,
                        item.profile_id,
                        item.source_game_id,
                        item.source_ply,
                        item.theme,
                        item.due_at,
                        _json(asdict(item)),
                    )
                    for item in practice
                ),
            )
            connection.executemany(
                "INSERT INTO lessons VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "data_json=excluded.data_json",
                ((item.id, item.profile_id, item.theme, _json(asdict(item))) for item in lessons),
            )

    def weakness_scores(self, profile_id: str = DEFAULT_PROFILE_ID) -> tuple[WeaknessScore, ...]:
        self.migrate()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT game_id, ply, theme, severity, confidence, outcome, created_at "
                "FROM weakness_events WHERE profile_id=? AND theme NOT IN "
                "(SELECT theme FROM dismissed_weaknesses WHERE profile_id=?)",
                (profile_id, profile_id),
            ).fetchall()
        from chesscoach.coach.weakness import aggregate_weaknesses

        events = tuple(
            WeaknessEvent(
                profile_id, game_id, ply, theme, severity, confidence, outcome, created_at
            )
            for game_id, ply, theme, severity, confidence, outcome, created_at in rows
        )
        return aggregate_weaknesses(events)

    def weakness_details(self, profile_id: str = DEFAULT_PROFILE_ID) -> tuple[WeaknessDetail, ...]:
        scores = {item.theme: item for item in self.weakness_scores(profile_id)}
        if not scores:
            return ()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT game_id, ply, theme, confidence, created_at FROM weakness_events "
                "WHERE profile_id=? AND outcome='observed' ORDER BY created_at DESC",
                (profile_id,),
            ).fetchall()
            analyses = connection.execute(
                "SELECT ar.game_id, ma.ply, ma.data_json FROM move_analyses ma "
                "JOIN analysis_runs ar ON ar.id=ma.run_id ORDER BY ar.updated_at DESC"
            ).fetchall()
        evidence_by_position: dict[tuple[str, int], tuple[Evidence, ...]] = {}
        for game_id, ply, data_json in analyses:
            key = (str(game_id), int(ply))
            if key not in evidence_by_position:
                evidence_by_position[key] = _move_from_dict(json.loads(data_json)).evidence
        now = datetime.now(UTC)
        grouped: dict[str, list[tuple[str, int, float, str]]] = {}
        for game_id, ply, theme, confidence, created_at in rows:
            if theme in scores:
                grouped.setdefault(str(theme), []).append(
                    (str(game_id), int(ply), float(confidence), str(created_at))
                )
        details = []
        for theme, score in scores.items():
            events = grouped.get(theme, [])
            recent = sum(
                1
                for *_, created_at in events
                if (now - datetime.fromisoformat(created_at)).days <= 45
            )
            earlier = len(events) - recent
            trend = "new" if not earlier else "improving" if recent < earlier else "needs attention"
            confidence = sum(event[2] for event in events) / len(events) if events else 0.0
            examples = tuple((event[0], event[1]) for event in events[:3])
            reason = next(
                (
                    fact.summary
                    for example in examples
                    for fact in evidence_by_position.get(example, ())
                    if fact.tag == theme
                ),
                f"Engine analysis tagged {theme.replace('_', ' ')} in saved positions.",
            )
            details.append(
                WeaknessDetail(
                    theme, score.score, score.occurrences, confidence, trend, examples, reason
                )
            )
        return tuple(details)

    def dismiss_weakness(self, theme: str, profile_id: str = DEFAULT_PROFILE_ID) -> None:
        self.migrate()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT OR REPLACE INTO dismissed_weaknesses VALUES (?, ?, ?)",
                (profile_id, theme, _now()),
            )

    def practice_items(self, profile_id: str = DEFAULT_PROFILE_ID) -> tuple[PracticeItem, ...]:
        self.migrate()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT data_json FROM practice_items WHERE profile_id=? ORDER BY due_at",
                (profile_id,),
            ).fetchall()
        return tuple(
            PracticeItem(
                **{
                    **data,
                    "solution": tuple(data["solution"]),
                    "alternatives": tuple(data["alternatives"]),
                    "alternative_lines": tuple(
                        tuple(line) for line in data.get("alternative_lines", ())
                    ),
                }
            )
            for data in (json.loads(row[0]) for row in rows)
        )

    def practice_progress(self, profile_id: str = DEFAULT_PROFILE_ID) -> PracticeProgress:
        self.migrate()
        now = _now()
        with closing(self._connect()) as connection:
            total, due = connection.execute(
                "SELECT COUNT(*), SUM(CASE WHEN due_at<=? THEN 1 ELSE 0 END) "
                "FROM practice_items WHERE profile_id=?",
                (now, profile_id),
            ).fetchone()
            attempted, successful = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(successful), 0) FROM practice_attempts "
                "WHERE item_id IN (SELECT id FROM practice_items WHERE profile_id=?)",
                (profile_id,),
            ).fetchone()
        return PracticeProgress(int(total), int(due or 0), int(attempted), int(successful))

    def previously_failed_practice_ids(
        self, profile_id: str = DEFAULT_PROFILE_ID
    ) -> frozenset[str]:
        """Return practice items with at least one unsuccessful attempt."""
        self.migrate()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT DISTINCT item_id FROM practice_attempts "
                "WHERE successful=0 AND item_id IN "
                "(SELECT id FROM practice_items WHERE profile_id=?)",
                (profile_id,),
            ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    def practice_transfer_observations(
        self, profile_id: str = DEFAULT_PROFILE_ID
    ) -> dict[str, tuple[tuple[bool, ...], tuple[bool, ...]]]:
        """Group failed and successful practice attempts by theme."""
        self.migrate()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT p.theme, a.successful FROM practice_attempts a "
                "JOIN practice_items p ON p.id=a.item_id WHERE p.profile_id=? "
                "ORDER BY a.attempted_at",
                (profile_id,),
            ).fetchall()
        grouped: dict[str, tuple[list[bool], list[bool]]] = {}
        for theme, successful in rows:
            before, after = grouped.setdefault(str(theme), ([], []))
            (after if successful else before).append(bool(successful))
        return {theme: (tuple(before), tuple(after)) for theme, (before, after) in grouped.items()}

    def lessons(self, profile_id: str = DEFAULT_PROFILE_ID) -> tuple[Lesson, ...]:
        self.migrate()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT lessons.data_json, COALESCE(lesson_progress.completed, 0) "
                "FROM lessons LEFT JOIN lesson_progress ON lesson_progress.lesson_id=lessons.id "
                "WHERE profile_id=? ORDER BY theme",
                (profile_id,),
            ).fetchall()
        return tuple(
            Lesson(
                **{
                    **json.loads(row[0]),
                    "recognition_cues": tuple(data["recognition_cues"]),
                    "exercise_ids": tuple(data["exercise_ids"]),
                    "completed": bool(row[1]),
                }
            )
            for row in rows
            for data in (json.loads(row[0]),)
        )

    def record_practice_attempt(
        self, item: PracticeItem, move_uci: str, successful: bool
    ) -> PracticeItem:
        updated = schedule_attempt(item, successful=successful)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO practice_attempts(item_id, attempted_at, move_uci, successful) "
                "VALUES (?, ?, ?, ?)",
                (item.id, _now(), move_uci, successful),
            )
            connection.execute(
                "UPDATE practice_items SET due_at=?, data_json=? WHERE id=?",
                (updated.due_at, _json(asdict(updated)), item.id),
            )
            if successful:
                connection.execute(
                    "INSERT INTO weakness_events(profile_id, game_id, ply, theme, severity, "
                    "confidence, outcome, created_at) VALUES (?, ?, ?, ?, 1, 1, 'mastered', ?) "
                    "ON CONFLICT(profile_id, game_id, ply, theme, outcome) DO UPDATE SET "
                    "created_at=excluded.created_at",
                    (
                        item.profile_id,
                        item.source_game_id,
                        item.source_ply,
                        item.theme,
                        _now(),
                    ),
                )
        return updated

    def lesson_step(self, lesson_id: str) -> int:
        self.migrate()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT step FROM lesson_progress WHERE lesson_id=?", (lesson_id,)
            ).fetchone()
        return int(row[0]) if row else 0

    def set_lesson_completed(
        self, lesson_id: str, completed: bool = True, *, step: int = 0
    ) -> None:
        self.migrate()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO lesson_progress(lesson_id, completed, updated_at, step) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(lesson_id) DO UPDATE SET "
                "completed=excluded.completed, updated_at=excluded.updated_at, step=excluded.step",
                (lesson_id, completed, _now(), step),
            )

    def enroll_course(self, course: Course, profile_id: str = DEFAULT_PROFILE_ID) -> None:
        """Create or update enrolment while preserving per-decision mastery."""
        self.migrate()
        first_module = course.modules[0].id if course.modules else ""
        now = _now()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT INTO course_progress(profile_id, course_id, content_version, "
                "last_module_id, "
                "completed, enrolled_at, updated_at) VALUES (?, ?, ?, ?, 0, ?, ?) "
                "ON CONFLICT(profile_id, course_id) DO UPDATE SET "
                "content_version=excluded.content_version, "
                "updated_at=excluded.updated_at",
                (profile_id, course.id, course.version, first_module, now, now),
            )
            for exercise in course.exercises:
                board = chess.Board(exercise.fen)
                learner = chess.WHITE if exercise.learner_color == "white" else chess.BLACK
                decision_index = 0
                for uci in exercise.line:
                    if board.turn == learner:
                        connection.execute(
                            "INSERT OR IGNORE INTO course_mastery(profile_id, course_id, "
                            "exercise_id, "
                            "decision_index, level, due_at, attempts, errors, hints, "
                            "last_result, updated_at) "
                            "VALUES (?, ?, ?, ?, 0, ?, 0, 0, 0, '', ?)",
                            (profile_id, course.id, exercise.id, decision_index, now, now),
                        )
                        decision_index += 1
                    board.push_uci(uci)

    def course_progress(
        self, course_id: str | None = None, profile_id: str = DEFAULT_PROFILE_ID
    ) -> tuple[CourseProgress, ...]:
        self.migrate()
        query = (
            "SELECT profile_id, course_id, content_version, last_module_id, completed, updated_at "
            "FROM course_progress WHERE profile_id=?"
        )
        params: tuple[object, ...] = (profile_id,)
        if course_id is not None:
            query += " AND course_id=?"
            params += (course_id,)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(
            CourseProgress(
                str(row[0]), str(row[1]), int(row[2]), str(row[3]), bool(row[4]), str(row[5])
            )
            for row in rows
        )

    def set_course_module(
        self,
        course_id: str,
        module_id: str,
        *,
        completed: bool = False,
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> None:
        self.migrate()
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE course_progress SET last_module_id=?, completed=?, updated_at=? "
                "WHERE profile_id=? AND course_id=?",
                (module_id, completed, _now(), profile_id, course_id),
            )

    def course_mastery(
        self, course_id: str, profile_id: str = DEFAULT_PROFILE_ID
    ) -> tuple[MoveMastery, ...]:
        self.migrate()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT profile_id, course_id, exercise_id, decision_index, level, due_at, "
                "attempts, "
                "errors, hints, last_result FROM course_mastery WHERE profile_id=? AND course_id=? "
                "ORDER BY exercise_id, decision_index",
                (profile_id, course_id),
            ).fetchall()
        return tuple(MoveMastery(*row) for row in rows)

    def due_course_mastery(
        self, profile_id: str = DEFAULT_PROFILE_ID, now: str | None = None
    ) -> tuple[MoveMastery, ...]:
        self.migrate()
        cutoff = now or _now()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT profile_id, course_id, exercise_id, decision_index, level, due_at, "
                "attempts, "
                "errors, hints, last_result FROM course_mastery WHERE profile_id=? AND due_at<=? "
                "ORDER BY due_at, course_id, exercise_id, decision_index",
                (profile_id, cutoff),
            ).fetchall()
        return tuple(MoveMastery(*row) for row in rows)

    def record_course_attempt(
        self,
        course_id: str,
        exercise_id: str,
        decision_index: int,
        move_uci: str,
        correct: bool,
        hints: int = 0,
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> MoveMastery:
        """Record one decision; a mistake affects only that decision's mastery."""
        self.migrate()
        now = datetime.now(UTC)
        current_level = 0
        with closing(self._connect()) as connection, connection:
            existing = connection.execute(
                "SELECT level FROM course_mastery WHERE profile_id=? AND course_id=? "
                "AND exercise_id=? AND decision_index=?",
                (profile_id, course_id, exercise_id, decision_index),
            ).fetchone()
            if existing:
                current_level = int(existing[0])
            due = next_course_due(current_level + (1 if correct else 0), correct, now)
            connection.execute(
                "INSERT INTO course_attempts(profile_id, course_id, exercise_id, decision_index, "
                "attempted_at, move_uci, correct, hints) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    profile_id,
                    course_id,
                    exercise_id,
                    decision_index,
                    now.isoformat(),
                    move_uci,
                    correct,
                    hints,
                ),
            )
            connection.execute(
                "INSERT INTO course_mastery(profile_id, course_id, exercise_id, "
                "decision_index, level, "
                "due_at, attempts, errors, hints, last_result, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?) "
                "ON CONFLICT(profile_id, course_id, exercise_id, decision_index) DO UPDATE SET "
                "level=MAX(0, course_mastery.level + excluded.level), due_at=excluded.due_at, "
                "attempts=course_mastery.attempts+1, errors=course_mastery.errors+excluded.errors, "
                "hints=course_mastery.hints+excluded.hints, "
                "last_result=excluded.last_result, updated_at=excluded.updated_at",
                (
                    profile_id,
                    course_id,
                    exercise_id,
                    decision_index,
                    1 if correct else 0,
                    due,
                    0 if correct else 1,
                    hints,
                    "correct" if correct else "mistake",
                    now.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT profile_id, course_id, exercise_id, decision_index, level, due_at, "
                "attempts, "
                "errors, hints, last_result FROM course_mastery WHERE profile_id=? AND course_id=? "
                "AND exercise_id=? AND decision_index=?",
                (profile_id, course_id, exercise_id, decision_index),
            ).fetchone()
        assert row is not None
        return MoveMastery(*row)
