"""Small, deterministic checks used by first-run setup and diagnostics."""

import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass(frozen=True)
class SetupChecks:
    dependencies_ready: bool
    storage_ready: bool
    engine_ready: bool


def check_storage(path: Path) -> bool:
    """Return whether the database directory can create and remove a file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=path.parent, prefix=".write-check-", delete=False) as file:
            probe = Path(file.name)
        probe.unlink()
    except OSError:
        return False
    return True


def check_engine(path: str) -> bool:
    """Return whether an engine path names a readable local file."""
    return bool(path and Path(path).is_file() and os.access(path, os.R_OK))


def run_setup_checks(database_path: Path, engine_path: str) -> SetupChecks:
    """Check runtime imports, storage, and the optional engine selection."""
    try:
        import chess  # noqa: F401
        import openai  # noqa: F401
        import PySide6  # noqa: F401
    except ImportError:
        dependencies = False
    else:
        dependencies = True
    return SetupChecks(dependencies, check_storage(database_path), check_engine(engine_path))
