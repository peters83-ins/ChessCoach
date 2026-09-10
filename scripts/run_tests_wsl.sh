#!/usr/bin/env bash
set -euo pipefail

# WSL must use a Linux virtual environment. The repository's .venv is a
# Windows environment and cannot be executed reliably through WSL interop.
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python_bin="${PYTHON:-python3}"
if ! command -v "$python_bin" >/dev/null 2>&1; then
    echo "Python 3.12+ is required. Set PYTHON to its executable." >&2
    exit 1
fi
if ! "$python_bin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "Python 3.12+ is required for Chess Coach." >&2
    exit 1
fi

venv_dir="$repo_root/.venv-wsl"
if [[ ! -x "$venv_dir/bin/python" ]]; then
    "$python_bin" -m venv "$venv_dir"
fi

"$venv_dir/bin/python" -m pip install --upgrade pip
"$venv_dir/bin/python" -m pip install -e '.[dev]'
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-offscreen}"
exec "$venv_dir/bin/python" -m pytest -q "$@"
