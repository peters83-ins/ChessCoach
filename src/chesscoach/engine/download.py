"""Verified, atomic Stockfish downloads for first-run setup."""

import hashlib
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import BinaryIO
from urllib.request import Request, urlopen


class EngineDownloadError(ValueError):
    """Raised when an engine artifact cannot be downloaded or verified."""


@dataclass(frozen=True)
class EngineArtifact:
    """Pinned platform-specific engine metadata."""

    url: str
    filename: str
    sha256: str
    version: str
    license_url: str

    def validate(self) -> None:
        digest = self.sha256.lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise EngineDownloadError("The configured Stockfish checksum is invalid.")
        if not self.url.startswith("https://") or not self.filename.strip():
            raise EngineDownloadError("The configured Stockfish download is invalid.")


OpenUrl = Callable[[Request], BinaryIO]


def download_engine(
    artifact: EngineArtifact,
    destination: Path,
    *,
    opener: OpenUrl = urlopen,
    cancelled: Event | None = None,
    chunk_size: int = 1024 * 1024,
) -> Path:
    """Download, hash-check, and atomically install one engine artifact."""
    artifact.validate()
    if chunk_size < 1:
        raise ValueError("Download chunk size must be positive.")
    stop = cancelled or Event()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".download")
    digest = hashlib.sha256()
    try:
        request = Request(artifact.url, headers={"User-Agent": "ChessCoach/1"})
        with opener(request) as response, temporary.open("wb") as output:
            while True:
                if stop.is_set():
                    raise EngineDownloadError("Stockfish download cancelled.")
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest().lower() != artifact.sha256.lower():
            raise EngineDownloadError("Stockfish checksum verification failed.")
        temporary.replace(destination)
        return destination
    except EngineDownloadError:
        temporary.unlink(missing_ok=True)
        raise
    except (OSError, ValueError) as error:
        temporary.unlink(missing_ok=True)
        raise EngineDownloadError(f"Could not download Stockfish: {error}") from error


def extract_engine_archive(
    archive: Path, destination: Path, *, executable_name: str = "stockfish.exe"
) -> Path:
    """Safely extract one engine executable from a verified archive."""
    temporary = destination.with_suffix(destination.suffix + ".download")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as source:
            candidates = [
                info
                for info in source.infolist()
                if not info.is_dir() and Path(info.filename).name.lower() == executable_name.lower()
            ]
            if len(candidates) != 1:
                raise EngineDownloadError("The Stockfish archive has no unique executable.")
            info = candidates[0]
            with source.open(info) as input_file, temporary.open("wb") as output:
                output.write(input_file.read())
        temporary.replace(destination)
        return destination
    except EngineDownloadError:
        temporary.unlink(missing_ok=True)
        raise
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        temporary.unlink(missing_ok=True)
        raise EngineDownloadError(f"Could not extract Stockfish: {error}") from error


def install_engine_archive(
    artifact: EngineArtifact,
    destination: Path,
    *,
    opener: OpenUrl = urlopen,
    cancelled: Event | None = None,
) -> Path:
    """Verify an archive and install its executable without partial files."""
    archive = destination.parent / artifact.filename
    try:
        download_engine(artifact, archive, opener=opener, cancelled=cancelled)
        return extract_engine_archive(archive, destination)
    finally:
        archive.unlink(missing_ok=True)
