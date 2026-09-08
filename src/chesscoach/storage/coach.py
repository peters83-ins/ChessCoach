"""Versioned SQLite storage for analysis, coaching, practice, and lessons."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

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
    WeaknessEvent,
    WeaknessScore,
)

SCHEMA_VERSION = 1
DEFAULT_PROFILE_ID = "default"


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
    )


class CoachRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def migrate(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=3.0)) as connection, connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise ValueError("The coaching database schema is newer than this application.")
            if version < 1:
                self._migration_one(connection)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

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
            "prompt_version TEXT NOT NULL, data_json TEXT NOT NULL, created_at TEXT NOT NULL, "
            "PRIMARY KEY(game_id, ply, provider, prompt_version))",
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

    def start_run(self, game_id: str, profile: AnalysisProfile) -> str:
        self.migrate()
        run_id = str(uuid4())
        now = _now()
        with closing(sqlite3.connect(self.path)) as connection, connection:
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
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "UPDATE analysis_runs SET state=?, completed=?, total=?, error=?, "
                "updated_at=? WHERE id=?",
                (state, completed, total, error, _now(), run_id),
            )

    def save_analysis(self, run_id: str, analysis: GameAnalysis) -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
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
        with closing(sqlite3.connect(self.path)) as connection:
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
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT player_color FROM games WHERE id=?", (game_id,)
            ).fetchone()
        return str(row[0]) if row else "white"

    def get_move_analysis(self, key: str) -> MoveAnalysis | None:
        if not self.path.is_file():
            return None
        with closing(sqlite3.connect(self.path)) as connection:
            try:
                row = connection.execute(
                    "SELECT data_json FROM analysis_cache WHERE cache_key=?", (key,)
                ).fetchone()
            except sqlite3.OperationalError:
                return None
        return _move_from_dict(json.loads(row[0])) if row else None

    def put_move_analysis(self, key: str, analysis: MoveAnalysis) -> None:
        self.migrate()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "INSERT INTO analysis_cache VALUES (?, ?, ?) ON CONFLICT(cache_key) DO UPDATE SET "
                "data_json=excluded.data_json, updated_at=excluded.updated_at",
                (key, _json(asdict(analysis)), _now()),
            )

    def save_feedback(self, feedback: tuple[CoachFeedback, ...]) -> None:
        if not feedback:
            return
        self.migrate()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.executemany(
                "INSERT INTO coach_feedback VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT DO UPDATE SET "
                "data_json=excluded.data_json, created_at=excluded.created_at",
                (
                    (
                        item.game_id,
                        item.ply,
                        item.provider,
                        item.prompt_version,
                        _json(asdict(item)),
                        _now(),
                    )
                    for item in feedback
                ),
            )

    def load_feedback(self, game_id: str) -> tuple[CoachFeedback, ...]:
        if not self.path.is_file():
            return ()
        with closing(sqlite3.connect(self.path)) as connection:
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
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.executemany(
                "INSERT INTO weakness_events(profile_id, game_id, ply, theme, severity, "
                "confidence, "
                "outcome, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(profile_id, game_id, ply, theme, outcome) DO UPDATE SET "
                "severity=excluded.severity, confidence=excluded.confidence, "
                "created_at=excluded.created_at",
                (
                    (
                        event.profile_id,
                        event.game_id,
                        event.ply,
                        event.theme,
                        event.severity,
                        event.confidence,
                        event.outcome,
                        _now(),
                    )
                    for event in events
                ),
            )
            connection.executemany(
                "INSERT INTO practice_items VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "due_at=excluded.due_at, data_json=excluded.data_json",
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
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT theme, severity, confidence, outcome FROM weakness_events "
                "WHERE profile_id=?",
                (profile_id,),
            ).fetchall()
        from chesscoach.coach.weakness import aggregate_weaknesses

        events = tuple(
            WeaknessEvent(profile_id, "", 0, theme, severity, confidence, outcome)
            for theme, severity, confidence, outcome in rows
        )
        return aggregate_weaknesses(events)

    def practice_items(self, profile_id: str = DEFAULT_PROFILE_ID) -> tuple[PracticeItem, ...]:
        self.migrate()
        with closing(sqlite3.connect(self.path)) as connection:
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
                }
            )
            for data in (json.loads(row[0]) for row in rows)
        )

    def lessons(self, profile_id: str = DEFAULT_PROFILE_ID) -> tuple[Lesson, ...]:
        self.migrate()
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT data_json FROM lessons WHERE profile_id=? ORDER BY theme", (profile_id,)
            ).fetchall()
        return tuple(
            Lesson(
                **{
                    **data,
                    "recognition_cues": tuple(data["recognition_cues"]),
                    "exercise_ids": tuple(data["exercise_ids"]),
                }
            )
            for data in (json.loads(row[0]) for row in rows)
        )
