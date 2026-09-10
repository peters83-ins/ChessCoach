from io import BytesIO
from pathlib import Path
from threading import Event

import pytest

from chesscoach.engine.download import (
    EngineArtifact,
    EngineDownloadError,
    download_engine,
    validate_uci_engine,
)


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
    with pytest.raises(EngineDownloadError):
        EngineArtifact(
            "https://example.test/file", "../file", "0" * 64, "1", "https://license"
        ).validate()
    with pytest.raises(EngineDownloadError):
        EngineArtifact(
            "https://example.test/file", "file", "0" * 64, "1", "http://license"
        ).validate()


class RedirectingResponse(BytesIO):
    def geturl(self) -> str:
        return "http://example.test/unsafe"


def test_download_rejects_insecure_redirect(tmp_path: Path) -> None:
    with pytest.raises(EngineDownloadError, match="insecure"):
        download_engine(
            artifact(b"payload"),
            tmp_path / "engine",
            opener=lambda _: RedirectingResponse(b"payload"),
        )


def test_download_size_limit_removes_partial_file(tmp_path: Path) -> None:
    target = tmp_path / "engine"
    with pytest.raises(EngineDownloadError, match="safety limit"):
        download_engine(
            artifact(b"payload"), target, opener=lambda _: BytesIO(b"payload"), max_bytes=3
        )
    assert not target.exists()
    assert not target.with_suffix(".download").exists()


def test_uci_validator_accepts_handshake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Process:
        def communicate(self, input: bytes, timeout: float) -> tuple[bytes, bytes]:
            return b"id name Stockfish 19\nuciok\n", b""

    monkeypatch.setattr(
        "chesscoach.engine.download.subprocess.Popen", lambda *args, **kwargs: Process()
    )
    validate_uci_engine(tmp_path / "stockfish.exe")


def test_uci_validator_rejects_malformed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        def communicate(self, input: bytes, timeout: float) -> tuple[bytes, bytes]:
            return b"id name unknown\n", b""

    monkeypatch.setattr(
        "chesscoach.engine.download.subprocess.Popen", lambda *args, **kwargs: Process()
    )
    with pytest.raises(EngineDownloadError, match="UCI handshake"):
        validate_uci_engine(tmp_path / "stockfish.exe")
