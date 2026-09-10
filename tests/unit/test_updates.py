import pytest

from chesscoach.updates import check_manifest


def manifest(version: str = "1.1.0", minimum: str = "1.0.0") -> dict[str, str]:
    return {
        "version": version,
        "minimum_supported_version": minimum,
        "installer_url": "https://example.test/installer.exe",
        "portable_url": "https://example.test/portable.zip",
        "sha256": "b" * 64,
        "release_notes_url": "https://example.test/release",
        "published_at": "2026-09-10T00:00:00Z",
    }


def test_new_release_is_reported() -> None:
    update = check_manifest(manifest(), "1.0.0")
    assert update is not None
    assert update.latest_version == "1.1.0"
    assert not update.mandatory


def test_current_release_is_not_reported() -> None:
    assert check_manifest(manifest("1.0.0"), "1.0.0") is None


def test_old_version_requires_update() -> None:
    update = check_manifest(manifest("1.1.0", "1.0.0"), "0.9.0")
    assert update is not None and update.mandatory


def test_invalid_versions_are_rejected() -> None:
    with pytest.raises(ValueError, match="version"):
        check_manifest(manifest("latest"), "1.0.0")
    with pytest.raises(ValueError, match="version"):
        check_manifest(manifest(), "development")
