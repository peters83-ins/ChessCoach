from pathlib import Path

from chesscoach.setup_checks import check_engine, check_storage, run_setup_checks


def test_setup_checks_storage_and_engine(tmp_path: Path) -> None:
    engine = tmp_path / "stockfish"
    engine.write_text("engine")
    database = tmp_path / "nested" / "games.sqlite3"
    assert check_storage(database)
    assert check_engine(str(engine))
    assert run_setup_checks(database, str(engine)).dependencies_ready


def test_missing_engine_is_not_ready(tmp_path: Path) -> None:
    assert not check_engine("")
    assert not check_engine(str(tmp_path / "missing"))
