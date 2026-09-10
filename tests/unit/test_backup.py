import sqlite3

import pytest

from chesscoach.storage.backup import BackupError, create_backup, restore_backup


def _db(path, marker: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker VALUES (?)", (marker,))


def test_backup_round_trip_restores_both_databases(tmp_path):
    games = tmp_path / "games.sqlite3"
    coach = tmp_path / "coach.sqlite3"
    _db(games, "games")
    _db(coach, "coach")
    archive = tmp_path / "backup.zip"
    create_backup(games, coach, archive)
    restored_games = tmp_path / "restored-games.sqlite3"
    restored_coach = tmp_path / "restored-coach.sqlite3"
    restore_backup(archive, restored_games, restored_coach)
    with sqlite3.connect(restored_games) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == ("games",)
    with sqlite3.connect(restored_coach) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == ("coach",)


def test_backup_rejects_missing_source_and_existing_destination(tmp_path):
    with pytest.raises(BackupError, match="must exist"):
        create_backup(tmp_path / "missing", tmp_path / "coach", tmp_path / "backup.zip")
    games = tmp_path / "games.sqlite3"
    coach = tmp_path / "coach.sqlite3"
    _db(games, "games")
    _db(coach, "coach")
    archive = tmp_path / "backup.zip"
    create_backup(games, coach, archive)
    with pytest.raises(BackupError, match="already exist"):
        restore_backup(archive, games, coach)


def test_backup_supports_application_shared_database_path(tmp_path):
    database = tmp_path / "games.sqlite3"
    _db(database, "shared")
    archive = tmp_path / "shared.zip"
    create_backup(database, database, archive)
    restored = tmp_path / "restored.sqlite3"
    restore_backup(archive, restored, restored)
    with sqlite3.connect(restored) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == ("shared",)
