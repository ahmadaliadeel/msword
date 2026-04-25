from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from msword.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("msword")
    app.setOrganizationName("msword")
    window = MainWindow()
    window.show()
    return app.exec()
