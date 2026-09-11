"""Run pytest for CI and avoid interpreter shutdown hangs from native Qt workers.

Pytest has already reported the result when ``pytest.main`` returns.  Windows
hosted runners can retain native Qt/engine threads during Python interpreter
shutdown, so CI exits with the recorded pytest status after flushing output.
"""

import os
import sys

import pytest


def main() -> None:
    status = pytest.main(sys.argv[1:] or ["-q"])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(status)


if __name__ == "__main__":
    main()
