import os
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def app() -> Iterator[QApplication]:
    application = QApplication.instance() or QApplication([])
    assert isinstance(application, QApplication)
    try:
        yield application
    finally:
        application.closeAllWindows()
        application.processEvents()
        application.quit()
        application.processEvents()


@pytest.fixture(autouse=True)
def no_optional_services(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "STOCKFISH_PATH"):
        monkeypatch.delenv(name, raising=False)
