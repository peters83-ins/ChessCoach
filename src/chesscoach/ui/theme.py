"""Modern, accessible application palette shared by the desktop UI."""

MODERN_STYLESHEET = """
QMainWindow, QDialog, QWidget { background: #f4f7fb; color: #172033; }
QToolBar { background: #172033; border: 0; padding: 8px 12px; spacing: 6px; }
QToolButton { color: #dce6ff; background: transparent; border: 0; border-radius: 7px;
              padding: 8px 12px; font-weight: 600; }
QToolButton:hover, QToolButton:checked { background: #33456f; color: #ffffff; }
QPushButton { background: #ffffff; color: #24324a; border: 1px solid #c9d3e3;
              border-radius: 8px; padding: 8px 14px; min-height: 18px; }
QPushButton:hover { background: #edf3ff; border-color: #6b86d9; }
QPushButton:pressed { background: #dce7ff; }
QPushButton:disabled { color: #9aa6b8; background: #e9edf3; border-color: #d8dee8; }
QPushButton#primaryAction { background: #4568d4; color: #ffffff; border-color: #4568d4;
                            font-weight: 700; }
QPushButton#primaryAction:hover { background: #3657bd; }
QLineEdit, QComboBox, QSpinBox { background: #ffffff; color: #172033; border: 1px solid #c9d3e3;
                                  border-radius: 7px; padding: 7px 9px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 2px solid #6280dd; padding: 6px 8px; }
QTableWidget, QListWidget { background: #ffffff; alternate-background-color: #f6f8fc;
                            border: 1px solid #d7dfec; border-radius: 8px;
                            gridline-color: #e6ebf3; }
QHeaderView::section { background: #e9eef8; color: #33415d; border: 0;
                       padding: 8px; font-weight: 700; }
QScrollArea { border: 0; background: transparent; }
QCheckBox { spacing: 8px; }
QLabel { color: #24324a; }
"""
