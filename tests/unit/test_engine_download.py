from io import BytesIO
from pathlib import Path
from threading import Event

import pytest

from chesscoach.engine.download import EngineArtifact, EngineDownloadError, download_engine


def artifact(content: bytes = b"stockfish") -> EngineArtifact:
    import hashlib

    return EngineArtifact(
        "https://example.test/stockfish.zip",
        "stockfish.zip",
        hashlib.sha256(content).hexdigest(),
        "17.1",
        "https://example.test/license",
    )


def test_download_verifies_and_replaces_atomically(tmp_path: Path) -> None:
    content = b"verified-engine"

    def opener(_request):
        return BytesIO(content)

    target = tmp_path / "engines" / "stockfish.zip"
    assert download_engine(artifact(content), target, opener=opener) == target
    assert target.read_bytes() == content
    assert not target.with_suffix(".zip.download").exists()


def test_download_rejects_bad_checksum_and_keeps_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "stockfish.zip"
    target.write_bytes(b"existing")

    with pytest.raises(EngineDownloadError, match="checksum"):
        download_engine(artifact(b"different"), target, opener=lambda _: BytesIO(b"wrong"))
    assert target.read_bytes() == b"existing"


def test_download_cancellation_removes_partial_file(tmp_path: Path) -> None:
    stop = Event()
    stop.set()
    target = tmp_path / "stockfish.zip"
    with pytest.raises(EngineDownloadError, match="cancelled"):
        download_engine(artifact(), target, opener=lambda _: BytesIO(b"data"), cancelled=stop)
    assert not target.exists()
    assert not target.with_suffix(".zip.download").exists()


def test_artifact_rejects_non_https_or_bad_digest() -> None:
    with pytest.raises(EngineDownloadError):
        EngineArtifact("http://example.test/file", "file", "0" * 64, "1", "license").validate()
    with pytest.raises(EngineDownloadError):
        EngineArtifact("https://example.test/file", "file", "bad", "1", "license").validate()
