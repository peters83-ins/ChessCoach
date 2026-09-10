"""Modern, accessible application palette shared by the desktop UI."""

MODERN_STYLESHEET = """
QMainWindow, QDialog, QWidget { background: #f4f7fb; color: #172033;
                                font-family: "Segoe UI", "Inter", sans-serif; font-size: 10pt; }
QMainWindow { font-size: 10pt; }
QToolBar { background: #172033; border: 0; padding: 8px 12px; spacing: 6px; }
QToolButton { color: #dce6ff; background: transparent; border: 0; border-radius: 7px;
              padding: 8px 12px; font-weight: 600; }
QToolButton:hover, QToolButton:checked { background: #33456f; color: #ffffff; }
QPushButton { background: #ffffff; color: #24324a; border: 1px solid #c9d3e3;
              border-radius: 8px; padding: 8px 14px; min-height: 20px; }
QPushButton:hover { background: #edf3ff; border-color: #6b86d9; }
QPushButton:pressed { background: #dce7ff; }
QPushButton:focus, QToolButton:focus, QCheckBox:focus, QSlider:focus {
    border: 2px solid #305da8;
    outline: none;
}
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
QTableWidget::item, QListWidget::item { padding: 6px; }
QTableWidget::item:selected, QListWidget::item:selected { background: #dce7ff; color: #172033; }
QHeaderView::section { background: #e9eef8; color: #33415d; border: 0;
                       padding: 8px; font-weight: 700; }
QScrollArea, QAbstractScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: #e9edf3; width: 12px; margin: 2px; border-radius: 6px; }
QScrollBar::handle:vertical { background: #9aa9c4; min-height: 32px; border-radius: 6px; }
QScrollBar::handle:vertical:hover { background: #6d82ad; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; height: 0; }
QScrollBar:horizontal { background: #e9edf3; height: 12px; margin: 2px; border-radius: 6px; }
QScrollBar::handle:horizontal { background: #9aa9c4; min-width: 32px; border-radius: 6px; }
QScrollBar::handle:horizontal:hover { background: #6d82ad; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent; width: 0;
}
QSlider::groove:horizontal { height: 6px; background: #d7dfec; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #6280dd; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; margin: -5px 0; background: #4568d4;
                               border: 2px solid #ffffff; border-radius: 8px; }
QProgressBar { background: #e9edf3; border: 0; border-radius: 6px;
               text-align: center; min-height: 12px; }
QProgressBar::chunk { background: #4568d4; border-radius: 6px; }
QCheckBox { spacing: 8px; }
QLabel { color: #24324a; }
QLabel[role="section"] { color: #172033; font-size: 12pt; font-weight: 700; }
QLabel[role="caption"] { color: #5f6f89; font-size: 9pt; }
QToolTip { background: #172033; color: #ffffff; border: 1px solid #6280dd; padding: 6px; }
"""
