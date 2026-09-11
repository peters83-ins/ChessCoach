import sqlite3
from pathlib import Path

import pytest

from chesscoach.storage.migration import MigrationError, migrate_with_backup


def database(path: Path, value: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE state (value TEXT NOT NULL)")
        connection.execute("INSERT INTO state VALUES (?)", (value,))


def read_value(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return str(connection.execute("SELECT value FROM state").fetchone()[0])


def test_successful_migration_keeps_backup(tmp_path: Path) -> None:
    games, coach, backup = (
        tmp_path / name for name in ("games.sqlite3", "coach.sqlite3", "before.zip")
    )
    database(games, "before")
    database(coach, "coach")

    migrate_with_backup(games, coach, backup, lambda: games.write_bytes(games.read_bytes()))

    assert backup.is_file()
    assert read_value(games) == "before"


def test_failed_migration_restores_original_databases(tmp_path: Path) -> None:
    games, coach, backup = (
        tmp_path / name for name in ("games.sqlite3", "coach.sqlite3", "before.zip")
    )
    database(games, "before")
    database(coach, "coach")

    def fail() -> None:
        connection = sqlite3.connect(games)
        try:
            connection.execute("UPDATE state SET value='broken'")
        finally:
            connection.close()
        raise ValueError("migration bug")

    with pytest.raises(MigrationError, match="restored"):
        migrate_with_backup(games, coach, backup, fail)
    assert read_value(games) == "before"
    assert read_value(coach) == "coach"
