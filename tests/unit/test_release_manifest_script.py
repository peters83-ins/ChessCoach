from pathlib import Path

from scripts.create_release_manifest import build_manifest


def test_build_manifest_points_to_release_assets_and_hashes_installer(tmp_path: Path) -> None:
    installer = tmp_path / "ChessCoach-0.1.0-windows-x64-setup.exe"
    portable = tmp_path / "ChessCoach-v0.1.0-windows-x64-portable.zip"
    installer.write_bytes(b"installer")
    portable.write_bytes(b"portable")

    manifest = build_manifest(
        version="0.1.0",
        repository="owner/chesscoach",
        tag="v0.1.0",
        installer=installer,
        portable=portable,
    )

    assert manifest["installer_url"].endswith(installer.name)
    assert manifest["portable_url"].endswith(portable.name)
    assert len(manifest["sha256"]) == 64
    assert manifest["minimum_supported_version"] == "0.1.0"
