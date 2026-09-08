from pathlib import Path

import pytest

from chesscoach.engine.discovery import discover_engine, engine_directory


def test_windows_local_engine_is_discovered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("chesscoach.engine.discovery.sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    directory = engine_directory()
    directory.mkdir(parents=True)
    engine = directory / "stockfish.exe"
    engine.touch()
    assert discover_engine() == str(engine)


def test_path_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("chesscoach.engine.discovery.engine_directory", lambda: tmp_path)
    monkeypatch.setattr("chesscoach.engine.discovery.shutil.which", lambda name: "path-engine")
    assert discover_engine() == "path-engine"
