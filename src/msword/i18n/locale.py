"""Locale helpers — RTL detection and locale tag normalization.

Pure functions only; no Qt imports here, so they are cheap to call from
model code, command code, and tests that don't spin up a ``QApplication``.
"""

from __future__ import annotations

# Languages whose dominant script is right-to-left. We match by the language
# subtag (the bit before the first ``_`` or ``-``) so callers may pass either
# a bare tag (``"ar"``) or a fully qualified locale (``"ar_EG"``, ``"ur-PK"``).
_RTL_LANGUAGES: frozenset[str] = frozenset(
    {
        "ar",  # Arabic
        "fa",  # Persian / Farsi
        "he",  # Hebrew
        "iw",  # legacy Hebrew tag
        "ur",  # Urdu
        "ps",  # Pashto
        "sd",  # Sindhi
        "ug",  # Uyghur
        "yi",  # Yiddish
        "ku",  # Kurdish (Sorani is RTL; Kurmanji is LTR — we err on the side of RTL)
        "dv",  # Dhivehi
    }
)


def language_subtag(locale: str) -> str:
    """Return the lowercase language subtag of *locale* (``"ar"`` from ``"ar_EG"``)."""
    if not locale:
        return ""
    # Accept both BCP-47 (``-``) and POSIX (``_``) separators.
    head = locale.replace("-", "_").split("_", 1)[0]
    return head.strip().lower()


def is_rtl_locale(locale: str) -> bool:
    """``True`` if *locale*'s language is written right-to-left.

    Examples:
        >>> is_rtl_locale("ar")
        True
        >>> is_rtl_locale("ur_PK")
        True
        >>> is_rtl_locale("en_US")
        False
    """
    return language_subtag(locale) in _RTL_LANGUAGES


__all__ = ["is_rtl_locale", "language_subtag"]
