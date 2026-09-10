from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from chesscoach.ui.evaluation_graph import EvaluationGraph


def test_evaluation_graph_click_maps_to_ply(app: QApplication) -> None:
    graph = EvaluationGraph()
    graph.values = (0.5, 0.6, 0.3, 0.8, 0.7)
    graph.resize(400, 100)
    graph.show()
    selected: list[int] = []
    graph.index_selected.connect(selected.append)
    QTest.mouseClick(graph, Qt.MouseButton.LeftButton, pos=graph.rect().center())
    assert selected == [2]
    image = graph.grab().toImage()
    assert not image.isNull()


def test_evaluation_graph_supports_keyboard_navigation(app: QApplication) -> None:
    graph = EvaluationGraph()
    graph.values = (0.5, 0.6, 0.3, 0.8)
    graph.set_selected(1)
    graph.show()
    selected: list[int] = []
    graph.index_selected.connect(selected.append)
    graph.setFocus()
    QTest.keyClick(graph, Qt.Key.Key_Right)
    QTest.keyClick(graph, Qt.Key.Key_Home)
    QTest.keyClick(graph, Qt.Key.Key_End)
    assert selected == [2, 0, 3]
    assert graph.focusPolicy().name == "StrongFocus"
    assert "Left and Right" in graph.accessibleDescription()
    graph.close()
