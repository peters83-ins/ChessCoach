import hashlib
import zipfile
from pathlib import Path

import pytest

from chesscoach.engine.artifacts import STOCKFISH_WINDOWS_X64
from chesscoach.engine.download import (
    EngineArtifact,
    EngineDownloadError,
    extract_engine_archive,
    install_engine_archive,
)


def test_windows_artifact_is_pinned() -> None:
    STOCKFISH_WINDOWS_X64.validate()
    assert STOCKFISH_WINDOWS_X64.version == "19"
    assert "/sf_19/" in STOCKFISH_WINDOWS_X64.url


def test_extract_engine_archive_atomically(tmp_path: Path) -> None:
    archive = tmp_path / "stockfish.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("stockfish/stockfish.exe", b"uci")
    destination = tmp_path / "engines" / "stockfish.exe"
    assert extract_engine_archive(archive, destination) == destination
    assert destination.read_bytes() == b"uci"


def test_extract_requires_unique_executable(tmp_path: Path) -> None:
    archive = tmp_path / "stockfish.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("a/stockfish.exe", b"a")
        output.writestr("b/stockfish.exe", b"b")
    with pytest.raises(EngineDownloadError, match="unique"):
        extract_engine_archive(archive, tmp_path / "stockfish.exe")


def test_extract_rejects_oversized_executable(tmp_path: Path) -> None:
    archive = tmp_path / "stockfish.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("stockfish/stockfish.exe", b"too large")
    with pytest.raises(EngineDownloadError, match="safety limit"):
        extract_engine_archive(archive, tmp_path / "stockfish.exe", max_bytes=3)


def test_install_removes_verified_archive_after_extraction(tmp_path: Path) -> None:
    payload = tmp_path / "payload.zip"
    with zipfile.ZipFile(payload, "w") as output:
        output.writestr("stockfish/stockfish.exe", b"uci")
    artifact = EngineArtifact(
        "https://example.test/stockfish.zip",
        "stockfish.zip",
        hashlib.sha256(payload.read_bytes()).hexdigest(),
        "test",
        "https://example.test/license",
    )

    class Response:
        def __init__(self) -> None:
            self.data = payload.read_bytes()

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int = -1) -> bytes:
            chunk, self.data = self.data[:size], self.data[size:]
            return chunk

    destination = tmp_path / "engine" / "stockfish.exe"
    install_engine_archive(artifact, destination, opener=lambda request: Response())
    assert destination.read_bytes() == b"uci"
    assert not (tmp_path / "engine" / "stockfish.zip").exists()
