import os

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QStackedWidget

from chesscoach.ui.navigation import Destination, WorkspaceNavigator


@pytest.fixture
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


def test_navigator_reuses_pages_and_supports_bounded_back_stack(app):
    stack = QStackedWidget()
    navigator = WorkspaceNavigator(stack, history_limit=2)
    pages = {}

    def page(name: str):
        return lambda: pages.setdefault(name, QLabel(name))

    navigator.show(Destination.PLAY, page("play"))
    first = navigator.show(Destination.COURSES, page("courses"))
    assert navigator.show(Destination.COURSES, page("other")) is first
    navigator.show(Destination.LEARN, page("learn"))
    navigator.show(Destination.INSIGHTS, page("insights"))
    assert len(navigator.history) == 2
    assert navigator.back() == Destination.LEARN
    assert navigator.current == Destination.LEARN
    assert navigator.forward() == Destination.INSIGHTS


def test_navigator_rejects_invalid_history_limit(app):
    with pytest.raises(ValueError):
        WorkspaceNavigator(QStackedWidget(), history_limit=0)


def test_primary_page_preserves_history_when_returning_to_play(app):
    stack = QStackedWidget()
    stack.addWidget(QLabel("play"))
    navigator = WorkspaceNavigator(stack)
    navigator.set_initial(Destination.PLAY)
    navigator.show(Destination.COURSES, lambda: QLabel("courses"))
    navigator.show_primary(Destination.PLAY)
    assert navigator.current == Destination.PLAY
    assert navigator.history == (Destination.PLAY.value, Destination.COURSES.value)
    assert navigator.back() == Destination.COURSES.value
