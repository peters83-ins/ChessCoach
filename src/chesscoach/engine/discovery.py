"""Find Stockfish in PATH or the app's per-user engine folder."""

import os
import shutil
import sys
from pathlib import Path


def engine_directory() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        base = Path(os.getenv("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "ChessCoach" / "engines"


def discover_engine() -> str:
    name = "stockfish.exe" if sys.platform == "win32" else "stockfish"
    local = engine_directory() / name
    return str(local) if local.is_file() else shutil.which(name) or ""
