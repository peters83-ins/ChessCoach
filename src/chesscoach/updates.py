"""Pure update-manifest validation and version comparison."""

import re
from dataclasses import dataclass
from typing import Any

from chesscoach.distribution import ReleaseManifest

_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    installer_url: str
    portable_url: str
    release_notes_url: str
    sha256: str
    mandatory: bool = False


def _version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported application version: {value!r}")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def check_manifest(payload: str | bytes | dict[str, Any], current: str) -> UpdateInfo | None:
    """Validate a release manifest and return an update only when needed."""
    current_tuple = _version(current)
    manifest = ReleaseManifest.from_json(payload)
    latest_tuple = _version(manifest.version)
    minimum_tuple = _version(manifest.minimum_supported_version)
    if latest_tuple <= current_tuple and current_tuple >= minimum_tuple:
        return None
    return UpdateInfo(
        current,
        manifest.version,
        manifest.installer_url,
        manifest.portable_url,
        manifest.release_notes_url,
        manifest.sha256,
        mandatory=current_tuple < minimum_tuple,
    )
