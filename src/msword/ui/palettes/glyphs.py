"""Glyphs palette — work unit #27.

A dockable palette that lets the user browse glyphs of a font, filtered by
Unicode block, with optional OpenType feature toggles. Double-clicking a
glyph emits :pyattr:`GlyphsPalette.glyph_inserted` with the glyph text so
the active text caret can insert it.

Design notes
------------
* Pure view: the palette never mutates the document. Insertion is signalled
  out and a Command in the controller layer is responsible for the actual
  document mutation.
* Pixmap rendering goes through a small per-(font, size, glyph, features)
  cache so toggling features re-renders only what changed. Toggling clears
  the cache because the rendered shape for many glyphs depends on the
  active feature set.
* Glyph coverage is determined via :pymeth:`QFontMetrics.inFontUcs4` per
  the spec.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtCore import QModelIndex, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPixmap,
    QStandardItem,
    QStandardItemModel,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFontComboBox,
    QHBoxLayout,
    QListView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Unicode blocks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Block:
    name: str
    start: int
    end: int  # inclusive

    def codepoints(self) -> Iterable[int]:
        return range(self.start, self.end + 1)


# A pragmatic subset of Unicode blocks covering Latin scripts, common
# European symbols, Arabic, Devanagari, plus typography niceties. Order
# matches the dropdown order presented to the user.
UNICODE_BLOCKS: tuple[_Block, ...] = (
    _Block("Basic Latin", 0x0020, 0x007E),
    _Block("Latin-1 Supplement", 0x00A0, 0x00FF),
    _Block("Latin Extended-A", 0x0100, 0x017F),
    _Block("Latin Extended-B", 0x0180, 0x024F),
    _Block("IPA Extensions", 0x0250, 0x02AF),
    _Block("Greek and Coptic", 0x0370, 0x03FF),
    _Block("Cyrillic", 0x0400, 0x04FF),
    _Block("Hebrew", 0x0590, 0x05FF),
    _Block("Arabic", 0x0600, 0x06FF),
    _Block("Devanagari", 0x0900, 0x097F),
    _Block("General Punctuation", 0x2000, 0x206F),
    _Block("Superscripts and Subscripts", 0x2070, 0x209F),
    _Block("Currency Symbols", 0x20A0, 0x20CF),
    _Block("Letterlike Symbols", 0x2100, 0x214F),
    _Block("Number Forms", 0x2150, 0x218F),
    _Block("Arrows", 0x2190, 0x21FF),
    _Block("Mathematical Operators", 0x2200, 0x22FF),
    _Block("Miscellaneous Symbols", 0x2600, 0x26FF),
    _Block("Dingbats", 0x2700, 0x27BF),
)


# OpenType features exposed as toggle buttons in the feature bar. Order
# matches the visual layout left-to-right.
FEATURE_TAGS: tuple[str, ...] = (
    "liga",
    "dlig",
    "smcp",
    "c2sc",
    "frac",
    "ordn",
    "tnum",
    "lnum",
    "ss01",
    "ss02",
    "ss03",
    "ss04",
    "ss05",
)


_GLYPH_PT = 36
_TILE = 48
_CODEPOINT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class GlyphsPalette(QDockWidget):
    """Dockable glyph picker with Unicode-block filter + OpenType toggles."""

    glyph_inserted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Glyphs", parent)
        self.setObjectName("GlyphsPalette")

        self._features: set[str] = set()
        self._cache: dict[tuple[str, int, str, frozenset[str]], QPixmap] = {}

        container = QWidget(self)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(4)

        self._font_combo = QFontComboBox(container)
        self._font_combo.currentFontChanged.connect(self._on_font_changed)
        outer.addWidget(self._font_combo)

        self._block_combo = QComboBox(container)
        for block in UNICODE_BLOCKS:
            self._block_combo.addItem(block.name)
        self._block_combo.currentIndexChanged.connect(self._on_block_changed)
        outer.addWidget(self._block_combo)

        self._feature_buttons: dict[str, QToolButton] = {}
        feature_bar = QWidget(container)
        bar_layout = QHBoxLayout(feature_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(2)
        for tag in FEATURE_TAGS:
            btn = QToolButton(feature_bar)
            btn.setText(tag)
            btn.setCheckable(True)
            btn.setToolTip(f"OpenType feature: {tag}")
            btn.toggled.connect(lambda checked, t=tag: self._on_feature_toggled(t, checked))
            bar_layout.addWidget(btn)
            self._feature_buttons[tag] = btn
        bar_layout.addStretch(1)
        outer.addWidget(feature_bar)

        self._view = QListView(container)
        self._view.setViewMode(QListView.ViewMode.IconMode)
        self._view.setResizeMode(QListView.ResizeMode.Adjust)
        self._view.setMovement(QListView.Movement.Static)
        self._view.setUniformItemSizes(True)
        self._view.setIconSize(QSize(_TILE, _TILE))
        self._view.setGridSize(QSize(_TILE + 6, _TILE + 6))
        self._view.setSpacing(2)
        self._model = QStandardItemModel(self._view)
        self._view.setModel(self._model)
        self._view.doubleClicked.connect(self._on_glyph_double_clicked)
        outer.addWidget(self._view, 1)

        self.setWidget(container)
        self._rebuild_grid()

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def set_font_family(self, family: str) -> None:
        """Set the active font family. Falls back gracefully if missing."""
        # Block signals to keep rebuild ordering deterministic; the combo's
        # signal also routes to ``_on_font_changed`` which would double-build.
        self._font_combo.blockSignals(True)
        self._font_combo.setCurrentFont(QFont(family))
        self._font_combo.blockSignals(False)
        self._invalidate_cache()
        self._rebuild_grid()

    def set_block(self, name: str) -> None:
        """Select a Unicode block by name."""
        idx = self._block_combo.findText(name)
        if idx < 0:
            return
        self._block_combo.blockSignals(True)
        self._block_combo.setCurrentIndex(idx)
        self._block_combo.blockSignals(False)
        self._rebuild_grid()

    def toggle_feature(self, tag: str) -> None:
        """Programmatically toggle an OpenType feature. Reshapes the grid."""
        if tag not in self._feature_buttons:
            return
        btn = self._feature_buttons[tag]
        btn.setChecked(not btn.isChecked())

    def active_features(self) -> frozenset[str]:
        return frozenset(self._features)

    def glyph_count(self) -> int:
        return self._model.rowCount()

    def cache_size(self) -> int:
        return len(self._cache)

    def find_glyph_index(self, text: str) -> QModelIndex:
        """Return the model index for a single-character glyph, or invalid."""
        if not text:
            return QModelIndex()
        target = ord(text[0])
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item is None:
                continue
            cp = item.data(_CODEPOINT_ROLE)
            if isinstance(cp, int) and cp == target:
                return self._model.index(row, 0)
        return QModelIndex()

    # -----------------------------------------------------------------
    # Internal — grid & cache
    # -----------------------------------------------------------------

    def _current_font(self) -> QFont:
        font = QFont(self._font_combo.currentFont())
        font.setPointSize(_GLYPH_PT)
        for tag in self._features:
            font.setFeature(QFont.Tag(tag), 1)
        return font

    def _current_block(self) -> _Block:
        idx = max(0, self._block_combo.currentIndex())
        return UNICODE_BLOCKS[idx]

    def _rebuild_grid(self) -> None:
        self._model.clear()
        font = self._current_font()
        family = font.family()
        metrics = QFontMetrics(font)
        block = self._current_block()
        features = self.active_features()

        for cp in block.codepoints():
            ch = chr(cp)
            # Skip control / format / surrogate / unassigned codepoints —
            # they would render as empty tofu.
            cat = unicodedata.category(ch)
            if cat[0] == "C":
                continue
            if not metrics.inFontUcs4(cp):
                continue
            pixmap = self._pixmap_for(family, _GLYPH_PT, ch, features, font)
            item = QStandardItem(QIcon(pixmap), "")
            item.setEditable(False)
            item.setData(cp, _CODEPOINT_ROLE)
            item.setSizeHint(QSize(_TILE + 6, _TILE + 6))
            try:
                name = unicodedata.name(ch)
            except ValueError:
                name = "<unnamed>"
            feat_text = ", ".join(sorted(features)) if features else "default"
            item.setToolTip(f"U+{cp:04X}  {name}\nfeatures: {feat_text}")
            self._model.appendRow(item)

    def _pixmap_for(
        self,
        family: str,
        pt: int,
        ch: str,
        features: frozenset[str],
        font: QFont,
    ) -> QPixmap:
        key = (family, pt, ch, features)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        pixmap = QPixmap(_TILE, _TILE)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), ch)
        finally:
            painter.end()
        self._cache[key] = pixmap
        return pixmap

    def _invalidate_cache(self) -> None:
        self._cache.clear()

    # -----------------------------------------------------------------
    # Internal — slots
    # -----------------------------------------------------------------

    def _on_font_changed(self, _font: QFont) -> None:
        self._invalidate_cache()
        self._rebuild_grid()

    def _on_block_changed(self, _index: int) -> None:
        self._rebuild_grid()

    def _on_feature_toggled(self, tag: str, checked: bool) -> None:
        if checked:
            self._features.add(tag)
        else:
            self._features.discard(tag)
        # Toggling a feature reshapes the grid: pixmap shapes may change
        # for many glyphs (e.g. ``liga`` collapses ``fi`` into one glyph).
        # Clear the cache and schedule the rebuild on the next event-loop
        # tick so the cache observably empties before being repopulated.
        self._invalidate_cache()
        QTimer.singleShot(0, self._rebuild_grid)

    def _on_glyph_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        item = self._model.itemFromIndex(index)
        if item is None:
            return
        cp = item.data(_CODEPOINT_ROLE)
        if not isinstance(cp, int):
            return
        self.glyph_inserted.emit(chr(cp))


__all__ = ["FEATURE_TAGS", "UNICODE_BLOCKS", "GlyphsPalette"]
