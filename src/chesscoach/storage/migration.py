"""Safe orchestration for additive application database migrations."""

from collections.abc import Callable
from pathlib import Path

from chesscoach.storage.backup import BackupError, create_backup, restore_backup


class MigrationError(RuntimeError):
    """Raised when a migration or its recovery cannot complete safely."""


def migrate_with_backup(
    game_database: Path,
    coach_database: Path,
    backup_path: Path,
    migrate: Callable[[], None],
) -> None:
    """Back up both databases, run ``migrate``, and restore on failure.

    The backup remains after a successful migration so it can support manual
    rollback. A failed migration never silently discards the original files.
    """
    try:
        create_backup(game_database, coach_database, backup_path)
    except BackupError as error:
        raise MigrationError(f"Could not create migration backup: {error}") from error
    try:
        migrate()
    except Exception as error:
        try:
            restore_backup(backup_path, game_database, coach_database, overwrite=True)
        except BackupError as recovery_error:
            raise MigrationError(
                f"Migration failed and recovery also failed: {recovery_error}"
            ) from error
        raise MigrationError("Migration failed; the original databases were restored.") from error
