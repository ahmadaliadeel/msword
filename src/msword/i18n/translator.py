"""Runtime translation infrastructure.

The :class:`LocaleManager` owns the currently-installed ``QTranslator`` and
emits :pyattr:`language_changed` whenever the UI language is swapped. It also
persists the user's choice via ``QSettings`` under the key
``"msword/language"`` so the next launch comes back up in the same language.

The ``.qm`` binaries are looked up next to this file, in the
``translations/`` package directory. ``.ts`` source files live there too;
the build step (Qt's ``pyside6-lupdate`` / ``pyside6-lrelease``) is
documented in :mod:`msword.i18n`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QSettings, QTranslator, Signal

_SETTINGS_KEY = "msword/language"
_TRANSLATIONS_DIR = Path(__file__).resolve().parent / "translations"


def tr(source: str) -> str:
    """Translate *source* in the ``"msword"`` translation context.

    Returns the source string unchanged if no translator is installed (or
    if the active translator has no entry for *source*) — callers therefore
    never have to special-case the bootstrap-before-language-load window.
    """
    return QCoreApplication.translate("msword", source)


class LocaleManager(QObject):
    """Owns the active ``QTranslator`` and broadcasts language changes.

    A single instance is expected per ``QApplication``. The currently
    installed translator (if any) is uninstalled before a new one is loaded
    so we never stack translators of different languages.
    """

    language_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._language: str = ""
        self._translator: QTranslator | None = None

    # ------------------------------------------------------------------ API

    @property
    def language(self) -> str:
        """The currently active language tag (``""`` until first load)."""
        return self._language

    def set_language(self, lang: str) -> bool:
        """Activate *lang*, install its ``.qm`` translator, persist + emit.

        Returns ``True`` if a ``.qm`` file was found and installed; ``False``
        if we fell back to the source strings. The signal is emitted in
        either case so subscribers can rebuild RTL-aware UI even when no
        translation catalogue exists yet (e.g. ``en_US``).
        """
        app = QCoreApplication.instance()
        # Uninstall any previously-installed translator so languages don't stack.
        if self._translator is not None and app is not None:
            app.removeTranslator(self._translator)
            self._translator = None

        installed = False
        qm_path = _TRANSLATIONS_DIR / f"{lang}.qm"
        if app is not None and qm_path.is_file():
            translator = QTranslator()
            if translator.load(str(qm_path)):
                app.installTranslator(translator)
                self._translator = translator
                installed = True

        self._language = lang
        QSettings().setValue(_SETTINGS_KEY, lang)
        self.language_changed.emit(lang)
        return installed

    def load_persisted(self, default: str = "en_US") -> str:
        """Load the persisted language (or *default*) and activate it."""
        stored = QSettings().value(_SETTINGS_KEY, default)
        lang = str(stored) if stored is not None else default
        self.set_language(lang)
        return lang


__all__ = ["LocaleManager", "tr"]
