from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("msword — Untitled")
        self.resize(1400, 900)
        placeholder = QLabel(
            "msword bootstrap.\n\n"
            "Menu bar, tools palette, measurements palette,\n"
            "page canvas, and dockable palettes will be wired in by\n"
            "their respective work units.",
            self,
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
