import json
from pathlib import Path

import pytest

from chesscoach.distribution import ReleaseManifest, resource_path, runtime_paths, user_data_dir


def test_user_data_dir_uses_windows_local_appdata(tmp_path: Path) -> None:
    assert user_data_dir(environ={"LOCALAPPDATA": str(tmp_path)}, platform="win32") == (
        tmp_path / "Chess Coach"
    )


def test_portable_paths_use_executable_directory(tmp_path: Path) -> None:
    paths = runtime_paths(executable=tmp_path / "ChessCoach.exe", portable=True)
    assert paths.data_dir == tmp_path / "data"
    assert paths.games_db == tmp_path / "data" / "games" / "games.sqlite3"


def test_release_manifest_validates_digest() -> None:
    payload = {
        "version": "0.2.0",
        "minimum_supported_version": "0.1.0",
        "installer_url": "https://example.test/installer.exe",
        "portable_url": "https://example.test/portable.zip",
        "sha256": "a" * 64,
        "release_notes_url": "https://example.test/notes",
        "published_at": "2026-09-10T00:00:00Z",
    }
    manifest = ReleaseManifest.from_json(json.dumps(payload))
    assert manifest.version == "0.2.0"
    assert manifest.sha256 == "a" * 64


def test_release_manifest_rejects_missing_or_invalid_fields() -> None:
    with pytest.raises(ValueError, match="required"):
        ReleaseManifest.from_json({})
    payload = {"version": "0.2.0", "minimum_supported_version": "0.1.0"}
    with pytest.raises(ValueError, match="required"):
        ReleaseManifest.from_json(payload)


def test_source_resource_path_resolves_packaged_course_content() -> None:
    assert resource_path("chesscoach/courses/content/courses.json").is_file()
