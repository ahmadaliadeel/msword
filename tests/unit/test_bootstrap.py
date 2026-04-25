from __future__ import annotations

import importlib


def test_package_imports() -> None:
    msword = importlib.import_module("msword")
    assert hasattr(msword, "__version__")


def test_main_window_constructs(qtbot) -> None:  # type: ignore[no-untyped-def]
    from msword.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle().startswith("msword")
