"""Network-independent update checking primitives.

The UI can run :class:`UpdateChecker.check` in a worker.  This module keeps
network access, throttling, and manifest validation out of the widgets.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from chesscoach.updates import UpdateInfo, check_manifest


class UpdateCheckError(RuntimeError):
    """Raised when an update manifest cannot be fetched or parsed."""


@dataclass(frozen=True)
class UpdateCheckResult:
    """Result of a check, including a user-safe status string."""

    update: UpdateInfo | None
    status: str
    checked_at: float


class UpdateChecker:
    """Fetch and cache a release manifest without blocking the application."""

    def __init__(
        self,
        manifest_url: str,
        current_version: str,
        cache_path: Path,
        *,
        interval_seconds: float = 86_400,
        opener: Callable[..., object] = urlopen,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.manifest_url = manifest_url
        self.current_version = current_version
        self.cache_path = cache_path
        self.interval_seconds = interval_seconds
        self._opener = opener
        self._clock = clock

    def should_check(self) -> bool:
        """Return false when a recent successful check is cached."""
        cached = self._read_cache()
        return cached is None or self._clock() - cached.checked_at >= self.interval_seconds

    def check(self, *, force: bool = False) -> UpdateCheckResult:
        """Fetch, validate, and cache a manifest; errors are recoverable."""
        cached = self._read_cache()
        if cached and not force and not self.should_check():
            return cached
        checked_at = self._clock()
        try:
            request = Request(self.manifest_url, headers={"User-Agent": "ChessCoach"})
            with self._opener(request, timeout=15) as response:  # type: ignore[attr-defined]
                payload = response.read()
            update = check_manifest(payload, self.current_version)
            result = UpdateCheckResult(
                update, "update available" if update else "up to date", checked_at
            )
            self._write_cache(result)
            return result
        except Exception as error:
            raise UpdateCheckError("Could not check for updates") from error

    def _read_cache(self) -> UpdateCheckResult | None:
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
            update_data = data.get("update")
            update = UpdateInfo(**update_data) if update_data else None
            return UpdateCheckResult(update, str(data["status"]), float(data["checked_at"]))
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write_cache(self, result: UpdateCheckResult) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "status": result.status,
            "checked_at": result.checked_at,
            "update": result.update.__dict__ if result.update else None,
        }
        temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        temporary.replace(self.cache_path)
