"""Create the release manifest consumed by the in-app update checker."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def sha256(path: Path) -> str:
    """Return the hexadecimal SHA-256 digest for an artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for block in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(
    *,
    version: str,
    repository: str,
    tag: str,
    installer: Path,
    portable: Path,
    release_notes_url: str | None = None,
) -> dict[str, str]:
    """Build a validated release manifest for GitHub Release assets."""
    if not version or not repository or not tag:
        raise ValueError("version, repository, and tag are required")
    if not installer.is_file() or not portable.is_file():
        raise FileNotFoundError("installer and portable artifacts must exist")
    base = f"https://github.com/{repository}/releases/download/{tag}"
    return {
        "version": version,
        "minimum_supported_version": version,
        "installer_url": f"{base}/{installer.name}",
        "portable_url": f"{base}/{portable.name}",
        "sha256": sha256(installer),
        "release_notes_url": release_notes_url
        or f"https://github.com/{repository}/releases/tag/{tag}",
        "published_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--portable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(
        version=args.version,
        repository=args.repository,
        tag=args.tag,
        installer=args.installer,
        portable=args.portable,
    )
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
