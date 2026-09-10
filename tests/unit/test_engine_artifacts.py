import zipfile
from pathlib import Path

import pytest

from chesscoach.engine.artifacts import STOCKFISH_WINDOWS_X64
from chesscoach.engine.download import EngineDownloadError, extract_engine_archive


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
