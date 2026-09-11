"""Run pytest for CI and avoid interpreter shutdown hangs from native Qt workers.

Pytest has already reported the result when ``pytest.main`` returns.  Windows
hosted runners can retain native Qt/engine threads during Python interpreter
shutdown, so CI exits with the recorded pytest status after flushing output.
"""

import os
import sys
from pathlib import Path

import pytest

# Running this file directly makes ``scripts`` Python's import root.  Keep the
# repository root importable so pytest collection behaves like ``python -m pytest``.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def main() -> None:
    status = pytest.main(sys.argv[1:] or ["-q"])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(status)


if __name__ == "__main__":
    main()
