"""Launch with python -m chesscoach.main or the chesscoach console command."""

import sys

from PySide6.QtWidgets import QApplication

from chesscoach.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Chess Coach")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
