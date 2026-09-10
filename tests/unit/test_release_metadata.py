import tomllib
from pathlib import Path

from chesscoach import __version__


def test_project_version_comes_from_package_source() -> None:
    document = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert document["project"]["dynamic"] == ["version"]
    assert document["tool"]["setuptools"]["dynamic"]["version"]["attr"] == "chesscoach.__version__"
    assert __version__.count(".") == 2
