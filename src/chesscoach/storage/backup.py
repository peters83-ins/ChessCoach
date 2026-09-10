"""Portable, atomic backup and restore for local Chess Coach databases."""

import os
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath


class BackupError(ValueError):
    """Raised when a backup archive is missing or contains an invalid database."""


def create_backup(game_database: Path, coach_database: Path, destination: Path) -> None:
    """Write both local databases to one compressed archive."""
    if not game_database.is_file() or not coach_database.is_file():
        raise BackupError("Both game and coaching databases must exist before backup.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(game_database, "games.sqlite3")
            if coach_database.resolve() != game_database.resolve():
                archive.write(coach_database, "coach.sqlite3")
        temporary.replace(destination)
    except (OSError, zipfile.BadZipFile) as error:
        temporary.unlink(missing_ok=True)
        raise BackupError(f"Could not create backup: {error}") from error


def _validate_database(path: Path) -> None:
    try:
        with closing(sqlite3.connect(path)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error as error:
        raise BackupError(f"Backup database is unreadable: {error}") from error
    if result != ("ok",):
        raise BackupError("Backup database failed SQLite integrity checks.")


def restore_backup(
    archive_path: Path, game_database: Path, coach_database: Path, *, overwrite: bool = False
) -> None:
    """Restore both databases, validating them before replacing local files."""
    if not archive_path.is_file():
        raise BackupError("Backup archive does not exist.")
    if not overwrite and (game_database.exists() or coach_database.exists()):
        raise BackupError("Destination databases already exist; choose overwrite explicitly.")
    temporary_dir = archive_path.parent / f".{archive_path.stem}-restore"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            if any(
                PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                for name in names
            ):
                raise BackupError("Backup contains an unsafe path.")
            if "games.sqlite3" not in names or (
                "coach.sqlite3" not in names and game_database.resolve() != coach_database.resolve()
            ):
                raise BackupError("Backup is missing a games or coaching database.")
            archive.extractall(temporary_dir)
            restored_games = temporary_dir / "games.sqlite3"
            restored_coach = (
                temporary_dir / "coach.sqlite3" if "coach.sqlite3" in names else restored_games
            )
        _validate_database(restored_games)
        _validate_database(restored_coach)
        game_database.parent.mkdir(parents=True, exist_ok=True)
        coach_database.parent.mkdir(parents=True, exist_ok=True)
        os.replace(restored_games, game_database)
        if coach_database.resolve() != game_database.resolve():
            os.replace(restored_coach, coach_database)
    except (OSError, zipfile.BadZipFile) as error:
        raise BackupError(f"Could not restore backup: {error}") from error
    finally:
        for child in temporary_dir.glob("*") if temporary_dir.exists() else ():
            child.unlink(missing_ok=True)
        temporary_dir.rmdir() if temporary_dir.exists() else None
