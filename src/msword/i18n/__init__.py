"""Internationalization for msword.

This package wires the runtime translation pipeline:

* :class:`~msword.i18n.translator.LocaleManager` — owns the active
  ``QTranslator``, persists the user's language choice via ``QSettings``
  under ``"msword/language"``, and emits ``language_changed(str)`` so RTL-aware
  views (see :mod:`msword.ui.rtl_shell`) can re-mirror.
* :func:`~msword.i18n.translator.tr` — thin wrapper over
  ``QCoreApplication.translate("msword", source)`` that returns the source
  string when no translator is installed.
* :func:`~msword.i18n.locale.is_rtl_locale` — pure helper used by the UI to
  decide whether to mirror layout direction.

Translation files live in :mod:`msword.i18n.translations`. We ship Qt
linguist sources (``en_US.ts``, ``ar.ts``, ``ur.ts``) under version control
and build ``.qm`` binaries at install time.

Build / refresh translations
----------------------------

To extract translatable strings from the source tree and refresh the ``.ts``
catalogues, then compile them to ``.qm``::

    pyside6-lupdate src/msword/**/*.py -ts src/msword/i18n/translations/en_US.ts
    pyside6-lupdate src/msword/**/*.py -ts src/msword/i18n/translations/ar.ts
    pyside6-lupdate src/msword/**/*.py -ts src/msword/i18n/translations/ur.ts

    pyside6-lrelease src/msword/i18n/translations/en_US.ts -qm src/msword/i18n/translations/en_US.qm
    pyside6-lrelease src/msword/i18n/translations/ar.ts    -qm src/msword/i18n/translations/ar.qm
    pyside6-lrelease src/msword/i18n/translations/ur.ts    -qm src/msword/i18n/translations/ur.qm

The ``.qm`` files are deliberately *not* checked in — they are build
artefacts, regenerated from the ``.ts`` sources.
"""

from __future__ import annotations

from msword.i18n.locale import is_rtl_locale, language_subtag
from msword.i18n.translator import LocaleManager, tr

__all__ = ["LocaleManager", "is_rtl_locale", "language_subtag", "tr"]
