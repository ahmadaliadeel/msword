"""Integration tests for the Glyphs palette (work unit #27).

Covers:
- Filtering by Unicode block (Basic Latin) shows ~all printable Latin glyphs.
- Double-clicking a glyph emits ``glyph_inserted`` with the glyph text.
- Toggling an OpenType feature clears the pixmap cache for the active font.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QDockWidget

from msword.ui.palettes.glyphs import GlyphsPalette


def _ensure_app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_basic_latin_block_yields_full_latin_set(qtbot) -> None:  # type: ignore[no-untyped-def]
    _ensure_app()
    palette = GlyphsPalette()
    qtbot.addWidget(palette)
    palette.set_font_family("DejaVu Sans")
    palette.set_block("Basic Latin")
    # DejaVu Sans covers the printable Basic Latin range; the spec quotes
    # ~95 glyphs, with a >=90 floor to allow for font variation.
    count = palette.glyph_count()
    assert count >= 90, f"expected >=90 Basic Latin glyphs, got {count}"


def test_double_click_emits_glyph_inserted(qtbot) -> None:  # type: ignore[no-untyped-def]
    _ensure_app()
    palette = GlyphsPalette()
    qtbot.addWidget(palette)
    palette.set_font_family("DejaVu Sans")
    palette.set_block("Basic Latin")

    received: list[str] = []
    palette.glyph_inserted.connect(received.append)

    # Triggering the double-click handler directly is robust against view
    # layout / coordinate mapping under offscreen Qt.
    index = palette.find_glyph_index("A")
    assert index.isValid(), "could not locate 'A' in glyph view"

    palette._on_glyph_double_clicked(index)  # type: ignore[attr-defined]
    assert received == ["A"]


def test_toggling_feature_clears_cache(qtbot) -> None:  # type: ignore[no-untyped-def]
    _ensure_app()
    palette = GlyphsPalette()
    qtbot.addWidget(palette)
    palette.set_font_family("DejaVu Sans")
    palette.set_block("Basic Latin")

    # Initial set_block already populates the pixmap cache.
    assert palette.glyph_count() > 0
    assert palette.cache_size() > 0

    palette.toggle_feature("liga")
    # Toggling reshapes the grid — cache for the previous feature set is gone.
    assert palette.cache_size() == 0


def test_palette_is_dock_widget(qtbot) -> None:  # type: ignore[no-untyped-def]
    _ensure_app()
    palette = GlyphsPalette()
    qtbot.addWidget(palette)

    assert isinstance(palette, QDockWidget)
    assert palette.windowTitle() == "Glyphs"
