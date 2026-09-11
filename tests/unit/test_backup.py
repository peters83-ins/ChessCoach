import sqlite3
import zipfile

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


def test_restore_rejects_unsafe_archive_path(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../games.sqlite3", b"not a database")
    with pytest.raises(BackupError, match="unsafe path"):
        restore_backup(archive, tmp_path / "games.sqlite3", tmp_path / "coach.sqlite3")


def test_restore_falls_back_when_replace_is_denied(tmp_path, monkeypatch):
    games = tmp_path / "games.sqlite3"
    coach = tmp_path / "coach.sqlite3"
    _db(games, "games")
    _db(coach, "coach")
    archive = tmp_path / "backup.zip"
    create_backup(games, coach, archive)

    import chesscoach.storage.backup as backup_module

    original_replace = backup_module.os.replace

    def deny_once(source, destination):
        backup_module.os.replace = original_replace
        raise PermissionError("simulated Windows denial")

    monkeypatch.setattr(backup_module.os, "replace", deny_once)
    restore_backup(archive, games, coach, overwrite=True)
    with sqlite3.connect(games) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == ("games",)
