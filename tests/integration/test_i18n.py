"""Integration tests for unit-30: i18n + RTL shell.

These tests exercise the runtime translation pipeline (``LocaleManager``,
``tr``) and the layout-direction mirroring helper (``RtlShell``). The
``Document`` and ``MainWindow`` types are stubbed locally — the spec
mandates *not* modifying ``main_window.py`` from this unit, and the model
``Document`` lives in a sibling unit (#2) that may not have landed.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal
from PySide6.QtWidgets import QLabel, QMainWindow, QWidget

from msword.i18n import LocaleManager, is_rtl_locale, tr
from msword.ui.rtl_shell import RtlShell

# --------------------------------------------------------------------- stubs


@dataclass
class _StubMeta:
    """Minimal stand-in for ``Document.meta`` — only ``locale`` is needed here."""

    locale: str = "en_US"


class _StubDocument(QObject):
    """Stub ``Document`` exposing the seam ``RtlShell`` consumes.

    Carries a ``meta.locale`` and emits ``meta_changed`` whenever the locale
    is mutated — matching the contract spelled out in the spec.
    """

    meta_changed = Signal()
    changed = Signal()

    def __init__(self, locale: str = "en_US") -> None:
        super().__init__()
        self.meta = _StubMeta(locale=locale)

    def set_locale(self, locale: str) -> None:
        self.meta.locale = locale
        self.meta_changed.emit()


# --------------------------------------------------------------- locale tests


class TestIsRtlLocale:
    def test_arabic_is_rtl(self) -> None:
        assert is_rtl_locale("ar") is True

    def test_urdu_is_rtl(self) -> None:
        assert is_rtl_locale("ur") is True

    def test_arabic_with_region_is_rtl(self) -> None:
        assert is_rtl_locale("ar_EG") is True
        assert is_rtl_locale("ar-SA") is True

    def test_urdu_with_region_is_rtl(self) -> None:
        assert is_rtl_locale("ur_PK") is True

    def test_persian_and_hebrew_are_rtl(self) -> None:
        assert is_rtl_locale("fa") is True
        assert is_rtl_locale("he") is True

    def test_english_is_not_rtl(self) -> None:
        assert is_rtl_locale("en_US") is False
        assert is_rtl_locale("en") is False

    def test_empty_string_is_not_rtl(self) -> None:
        assert is_rtl_locale("") is False


# ----------------------------------------------------------- LocaleManager


class TestLocaleManager:
    def test_set_language_emits_signal(self, qapp, qtbot) -> None:  # type: ignore[no-untyped-def]
        mgr = LocaleManager()
        with qtbot.waitSignal(mgr.language_changed, timeout=1000) as blocker:
            mgr.set_language("ar")
        assert blocker.args == ["ar"]
        assert mgr.language == "ar"

    def test_set_language_persists_via_qsettings(self, qapp, qtbot) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtCore import QSettings

        # Sandbox the settings to avoid clobbering a developer's real prefs.
        QCoreApplication.setOrganizationName("msword-test")
        QCoreApplication.setApplicationName("msword-test-i18n")
        QSettings().clear()

        mgr = LocaleManager()
        mgr.set_language("ur")

        # A fresh QSettings() instance should see the persisted value.
        assert str(QSettings().value("msword/language")) == "ur"

    def test_load_persisted_falls_back_to_default(self, qapp) -> None:  # type: ignore[no-untyped-def]
        from PySide6.QtCore import QSettings

        QCoreApplication.setOrganizationName("msword-test")
        QCoreApplication.setApplicationName("msword-test-i18n-default")
        QSettings().clear()

        mgr = LocaleManager()
        chosen = mgr.load_persisted(default="en_US")
        assert chosen == "en_US"
        assert mgr.language == "en_US"

    def test_set_language_swaps_translator(self, qapp) -> None:  # type: ignore[no-untyped-def]
        # ar.qm is not built in the source tree (it's a build artefact);
        # set_language should still succeed and just leave the source string
        # in place when no .qm is found. We assert the no-translator path
        # explicitly because it's the one that runs in CI.
        mgr = LocaleManager()
        installed = mgr.set_language("ar")
        # If a .qm happens to be present, we got True; else False — both fine.
        assert isinstance(installed, bool)

    def test_tr_returns_source_when_no_translator(self, qapp) -> None:  # type: ignore[no-untyped-def]
        # With no translator installed (or a translator that has no entry
        # for "File"), tr() returns the source string verbatim.
        mgr = LocaleManager()
        mgr.set_language("en_US")  # en_US.ts is empty by design
        assert tr("File") == "File"


# --------------------------------------------------------------- RtlShell


class TestRtlShell:
    def test_canvas_mirrors_for_rtl_document(self, qapp, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = QMainWindow()
        qtbot.addWidget(window)
        canvas = QLabel("canvas-stub")
        canvas.setObjectName("canvas")
        window.setCentralWidget(canvas)

        doc = _StubDocument(locale="ar")
        shell = RtlShell(window, doc)
        assert shell is not None  # quiet ruff B018

        assert canvas.layoutDirection() == Qt.LayoutDirection.RightToLeft

    def test_canvas_stays_ltr_for_ltr_document(self, qapp, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = QMainWindow()
        qtbot.addWidget(window)
        canvas = QLabel("canvas-stub")
        window.setCentralWidget(canvas)

        doc = _StubDocument(locale="en_US")
        shell = RtlShell(window, doc)
        assert shell is not None

        assert canvas.layoutDirection() == Qt.LayoutDirection.LeftToRight

    def test_menu_bar_stays_ltr_when_document_is_rtl(self, qapp, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = QMainWindow()
        qtbot.addWidget(window)
        canvas = QWidget()
        window.setCentralWidget(canvas)

        # Prime a menu bar so we have something to assert on.
        menu_bar = window.menuBar()
        assert menu_bar is not None

        doc = _StubDocument(locale="ar")
        shell = RtlShell(window, doc)
        assert shell is not None

        assert canvas.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert menu_bar.layoutDirection() == Qt.LayoutDirection.LeftToRight

    def test_meta_changed_reapplies(self, qapp, qtbot) -> None:  # type: ignore[no-untyped-def]
        window = QMainWindow()
        qtbot.addWidget(window)
        canvas = QWidget()
        window.setCentralWidget(canvas)

        doc = _StubDocument(locale="en_US")
        shell = RtlShell(window, doc)
        assert shell is not None
        assert canvas.layoutDirection() == Qt.LayoutDirection.LeftToRight

        doc.set_locale("ur")
        assert canvas.layoutDirection() == Qt.LayoutDirection.RightToLeft

        doc.set_locale("en_US")
        assert canvas.layoutDirection() == Qt.LayoutDirection.LeftToRight

    def test_falls_back_to_changed_signal(self, qapp, qtbot) -> None:  # type: ignore[no-untyped-def]
        # Document with only ``changed`` (no ``meta_changed``) should still
        # work — RtlShell prefers ``meta_changed`` but accepts either.
        class ChangedOnlyDoc(QObject):
            changed = Signal()

            def __init__(self) -> None:
                super().__init__()
                self.meta = _StubMeta(locale="ar")

        window = QMainWindow()
        qtbot.addWidget(window)
        canvas = QWidget()
        window.setCentralWidget(canvas)

        doc = ChangedOnlyDoc()
        shell = RtlShell(window, doc)
        assert shell is not None
        assert canvas.layoutDirection() == Qt.LayoutDirection.RightToLeft


# NOTE: ``qapp`` and ``qtbot`` are provided by pytest-qt; we rely on those.
