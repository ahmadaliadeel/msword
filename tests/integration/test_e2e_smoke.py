"""End-to-end smoke test.

Each work unit (per spec §13) may *add* steps to this file as it lands new
features. No unit may remove or weaken existing steps.
"""

from __future__ import annotations


def test_app_launches(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Bootstrap-level smoke: the main window can be constructed and shown."""
    from msword.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert window.isVisible()
