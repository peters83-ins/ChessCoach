# Contributing and Windows releases

## Local development

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev,ai]"
\.venv\Scripts\python -m pytest -q
```

Use `QT_QPA_PLATFORM=offscreen` for headless checks. Keep API keys in an ignored
`.env`; never commit them or put them in release artifacts.

## Build the Windows payload

Install the build extra and run:

```powershell
python -m pip install ".[build]"
pyinstaller --clean --noconfirm packaging/chesscoach.spec
Compress-Archive -Path dist/ChessCoach/* -DestinationPath dist/ChessCoach-portable.zip
```

The payload is portable. It stores data beside the executable only when the
`data` directory is writable; installed builds otherwise use `%LOCALAPPDATA%\ChessCoach`.

## Build the installer

Install [Inno Setup](https://jrsoftware.org/isinfo.php), then run:

```powershell
iscc /DAppVersion=0.1.0 packaging/ChessCoach.iss
```

The installer does not remove user databases during uninstall. Release signing
is performed by the protected CI environment; signing certificates and passwords
must be supplied as repository secrets and never committed.

## Release checklist

1. Update `chesscoach.__version__` and release notes.
2. Run Ruff, mypy, the full test suite, and the real-Stockfish tests.
3. Create an annotated `v<version>` tag from the validated commit.
4. Let the Windows workflow build the executable, portable ZIP, installer, and checksums.
5. Verify SHA-256 values and test install, upgrade, launch, save/load, and uninstall.

GitHub Releases remains the distribution source. Keep the previous release available
so users can roll back after a failed upgrade.
