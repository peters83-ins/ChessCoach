"""Typed navigation state for the single-workspace desktop shell."""

from collections import deque
from collections.abc import Callable
from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStackedWidget, QWidget


class Destination(StrEnum):
    PLAY = "play"
    GAMES = "games"
    REVIEW = "review"
    PRACTICE = "practice"
    LEARN = "learn"
    LESSONS = "lessons"
    COURSES = "courses"
    INSIGHTS = "insights"
    SETTINGS = "settings"
    DIAGNOSTICS = "diagnostics"
    SANDBOX = "sandbox"
    TOOLS = "tools"


class WorkspaceNavigator:
    """Own one page instance per destination and a bounded back stack."""

    def __init__(self, stack: QStackedWidget, *, history_limit: int = 20) -> None:
        if history_limit < 1:
            raise ValueError("Navigation history must retain at least one entry.")
        self.stack = stack
        self.history_limit = history_limit
        self.pages: dict[str, QWidget] = {}
        self._history: deque[str] = deque(maxlen=history_limit)
        self._forward: deque[str] = deque(maxlen=history_limit)
        self._current: str | None = None
        self._moving_back = False

    @property
    def current(self) -> str | None:
        return self._current

    @property
    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    def set_initial(self, destination: Destination | str) -> None:
        """Declare the already-installed landing page without adding history."""
        self._current = destination.value if isinstance(destination, Destination) else destination

    def show(self, destination: Destination | str, factory: Callable[[], QWidget]) -> QWidget:
        key = destination.value if isinstance(destination, Destination) else destination
        page = self.pages.get(key)
        if page is None:
            page = factory()
            page.setParent(self.stack)
            page.setWindowFlags(Qt.WindowType.Widget)
            self.pages[key] = page
            self.stack.addWidget(page)
        if self._current != key and not self._moving_back:
            if self._current is not None:
                self._history.append(self._current)
            self._forward.clear()
        self._current = key
        self.stack.setCurrentWidget(page)
        page.show()
        page.raise_()
        page.activateWindow()
        return page

    def back(self) -> str | None:
        if not self._history:
            return self._current
        destination = self._history.pop()
        if self._current is not None:
            self._forward.append(self._current)
        if destination == Destination.PLAY.value:
            self._moving_back = True
            try:
                self._current = destination
                self.stack.setCurrentIndex(0)
            finally:
                self._moving_back = False
            return destination
        page = self.pages.get(destination)
        if page is None:
            return self._current
        self._moving_back = True
        try:
            self._current = destination
            self.stack.setCurrentWidget(page)
            page.show()
            page.raise_()
            page.activateWindow()
        finally:
            self._moving_back = False
        return destination

    def forward(self) -> str | None:
        """Return to the next page after a back navigation."""
        if not self._forward:
            return self._current
        destination = self._forward.pop()
        if self._current is not None:
            self._history.append(self._current)
        if destination == Destination.PLAY.value:
            self._current = destination
            self.stack.setCurrentIndex(0)
            return destination
        page = self.pages.get(destination)
        if page is None:
            return self._current
        self._current = destination
        self.stack.setCurrentWidget(page)
        page.show()
        page.raise_()
        page.activateWindow()
        return destination

    def clear(self) -> None:
        self._history.clear()
        self._forward.clear()
        self._current = None
        for page in tuple(self.pages.values()):
            page.close()
            page.deleteLater()
        self.pages.clear()
