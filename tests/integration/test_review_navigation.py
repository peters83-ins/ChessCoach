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
