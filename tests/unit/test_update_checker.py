from pathlib import Path

import pytest

from chesscoach.update_checker import UpdateChecker, UpdateCheckError

MANIFEST = b'''{"version":"1.1.0","minimum_supported_version":"1.0.0",
"installer_url":"https://example.test/app.exe","portable_url":"https://example.test/app.zip",
"sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
"release_notes_url":"https://example.test/notes","published_at":"2026-09-10T00:00:00Z"}'''


class Response:
    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return MANIFEST


def test_checker_fetches_and_caches(tmp_path: Path) -> None:
    calls: list[object] = []
    checker = UpdateChecker("https://example.test/manifest.json", "1.0.0", tmp_path / "update.json",
                            opener=lambda request, timeout: calls.append(request) or Response())
    result = checker.check()
    assert result.update is not None
    assert checker.should_check() is False
    assert checker.check() == result
    assert len(calls) == 1


def test_force_check_ignores_cache(tmp_path: Path) -> None:
    calls: list[object] = []
    checker = UpdateChecker("https://example.test/manifest.json", "1.0.0", tmp_path / "update.json",
                            opener=lambda request, timeout: calls.append(request) or Response())
    checker.check()
    checker.check(force=True)
    assert len(calls) == 2


def test_network_failure_is_safe(tmp_path: Path) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise OSError("offline")

    checker = UpdateChecker(
        "https://example.test/manifest.json", "1.0.0", tmp_path / "update.json", opener=fail
    )
    with pytest.raises(UpdateCheckError, match="Could not check"):
        checker.check()
