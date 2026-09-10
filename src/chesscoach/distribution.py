"""Runtime paths and release metadata used by installed desktop builds."""

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chesscoach import __version__


@dataclass(frozen=True)
class AppPaths:
    """User-writable locations for one Chess Coach installation."""

    data_dir: Path

    @property
    def games_db(self) -> Path:
        return self.data_dir / "games" / "games.sqlite3"

    @property
    def coach_db(self) -> Path:
        return self.data_dir / "games" / "coach.sqlite3"

    @property
    def engine_dir(self) -> Path:
        return self.data_dir / "engines"


def user_data_dir(*, environ: dict[str, str] | None = None, platform: str | None = None) -> Path:
    """Return the conventional per-user directory without creating it."""
    values = environ if environ is not None else os.environ
    system = platform or sys.platform
    if system == "win32":
        base = Path(values.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(values.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "Chess Coach"


def runtime_paths(*, executable: Path | None = None, portable: bool = False) -> AppPaths:
    """Choose installed or portable data paths with a writable fallback."""
    if portable:
        location = (executable or Path(sys.executable)).resolve().parent / "data"
        try:
            location.mkdir(parents=True, exist_ok=True)
            probe = location / ".write-check"
            probe.touch()
            probe.unlink()
            return AppPaths(location)
        except OSError:
            pass
    return AppPaths(user_data_dir())


@dataclass(frozen=True)
class ReleaseManifest:
    """Validated metadata published beside a GitHub release."""

    version: str
    minimum_supported_version: str
    installer_url: str
    portable_url: str
    sha256: str
    release_notes_url: str
    published_at: str

    @classmethod
    def from_json(cls, payload: str | bytes | dict[str, Any]) -> "ReleaseManifest":
        data = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        required = (
            "version",
            "minimum_supported_version",
            "installer_url",
            "portable_url",
            "sha256",
            "release_notes_url",
            "published_at",
        )
        if not isinstance(data, dict) or any(
            not isinstance(data.get(key), str) for key in required
        ):
            raise ValueError("Release manifest is missing required string fields.")
        digest = str(data["sha256"]).lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("Release manifest contains an invalid SHA-256 digest.")
        return cls(
            str(data["version"]),
            str(data["minimum_supported_version"]),
            str(data["installer_url"]),
            str(data["portable_url"]),
            digest,
            str(data["release_notes_url"]),
            str(data["published_at"]),
        )


def current_version() -> str:
    """Return the single application version used by UI and release tooling."""
    return __version__


def resource_path(relative: str | Path) -> Path:
    """Resolve packaged assets in source checkouts and PyInstaller bundles."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative
