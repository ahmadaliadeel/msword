"""Style sheets palette — work unit #25.

Dockable QuarkXPress-style palette listing paragraph and character
styles in two tabs, with a New / Duplicate / Delete / Edit / Apply
toolbar. Each list row shows the style's name plus a mini "Aa Bb Cc 123"
preview rendered with QFontMetrics + QPixmap so users can read the
paragraph style at a glance.

All mutations dispatch a Command (per the spec's anchor invariant); the
view never touches the model directly.
"""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QFont, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from msword.commands import (
    AddCharacterStyleCommand,
    AddParagraphStyleCommand,
    ApplyCharacterStyleCommand,
    ApplyParagraphStyleCommand,
    DeleteCharacterStyleCommand,
    DeleteParagraphStyleCommand,
    DuplicateCharacterStyleCommand,
    DuplicateParagraphStyleCommand,
)
from msword.commands.base import Document as CommandDocument
from msword.model.document import Document
from msword.model.style import (
    CharacterStyle,
    ParagraphStyle,
    Style,
)
from msword.ui.palettes._style_editor_dialog import StyleEditorDialog

_PREVIEW_TEXT = "Aa Bb Cc 123"
_PREVIEW_SIZE = QSize(160, 28)


def _resolve_attr(registry: dict[str, Style], name: str, attr: str) -> Any:
    """Walk the based-on chain returning the first non-None value of `attr`.

    A self-contained traversal avoids tying us to `StyleResolver`'s
    `TypeVar` constraint (which doesn't accept the heterogeneous union).
    Cycles short-circuit silently — defence in depth; cycle detection is
    enforced at edit time by `EditParagraphStyleCommand`.
    """
    seen: set[str] = set()
    current: str | None = name
    while current is not None and current not in seen:
        seen.add(current)
        style = registry.get(current)
        if style is None:
            return None
        value = getattr(style, attr, None)
        if value is not None:
            return value
        current = style.based_on
    return None


def _resolved_font(registry: dict[str, Style], name: str) -> QFont:
    """Resolve a style's typographic properties up the based-on chain
    and produce a :class:`QFont` for the row preview. Falls back to
    sensible defaults so the preview is always readable.
    """
    family = _resolve_attr(registry, name, "font_family") or "Sans Serif"
    size = _resolve_attr(registry, name, "font_size_pt") or 12.0
    font = QFont(str(family))
    font.setPointSizeF(float(size))
    if _resolve_attr(registry, name, "bold"):
        font.setBold(True)
    if _resolve_attr(registry, name, "italic"):
        font.setItalic(True)
    if _resolve_attr(registry, name, "underline"):
        font.setUnderline(True)
    return font


def _render_preview(font: QFont, *, size: QSize = _PREVIEW_SIZE) -> QPixmap:
    """Render *_PREVIEW_TEXT* at the resolved font into a QPixmap.

    Used for the per-row mini preview. We size the pixmap to the
    QListWidget icon size; QFontMetrics gives us baseline alignment.
    """
    pix = QPixmap(size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setFont(font)
        metrics = QFontMetrics(font)
        baseline = (size.height() + metrics.ascent() - metrics.descent()) // 2
        painter.drawText(2, baseline, _PREVIEW_TEXT)
    finally:
        painter.end()
    return pix


class StyleSheetsPalette(QDockWidget):
    """Paragraph + character styles dock palette."""

    OBJECT_NAME = "StyleSheetsPalette"

    def __init__(self, document: Document, parent: QWidget | None = None) -> None:
        super().__init__("Style Sheets", parent)
        self.setObjectName(self.OBJECT_NAME)
        self._document = document
        # Commands take the structural-Protocol Document defined in
        # commands.base; the model Document satisfies the subset they
        # actually call (changed signal + style lists + selection).
        self._cmd_doc = cast(CommandDocument, document)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._toolbar = QToolBar("Style sheet actions", container)
        self._toolbar.setIconSize(QSize(16, 16))
        self._action_new = QAction(QIcon(), "New", self)
        self._action_new.setToolTip("New style")
        self._action_new.setText("+")
        self._action_duplicate = QAction(QIcon(), "Duplicate", self)
        self._action_duplicate.setToolTip("Duplicate selected style")
        self._action_delete = QAction(QIcon(), "Delete", self)
        self._action_delete.setToolTip("Delete selected style")
        self._action_edit = QAction(QIcon(), "Edit", self)
        self._action_edit.setToolTip("Edit selected style")
        self._action_apply = QAction(QIcon(), "Apply", self)
        self._action_apply.setToolTip("Apply style to current selection")
        for act in (
            self._action_new,
            self._action_duplicate,
            self._action_delete,
            self._action_edit,
            self._action_apply,
        ):
            self._toolbar.addAction(act)

        self._action_new.triggered.connect(self._on_new)
        self._action_duplicate.triggered.connect(self._on_duplicate)
        self._action_delete.triggered.connect(self._on_delete)
        self._action_edit.triggered.connect(self._on_edit)
        self._action_apply.triggered.connect(self._on_apply)

        layout.addWidget(self._toolbar)

        self._tabs = QTabWidget(container)
        self._paragraph_list = self._make_list()
        self._character_list = self._make_list()
        self._tabs.addTab(self._paragraph_list, "Paragraph")
        self._tabs.addTab(self._character_list, "Character")
        layout.addWidget(self._tabs)

        self.setWidget(container)
        self.refresh()

    # ------------------------------------------------------------------
    # tab + list helpers
    # ------------------------------------------------------------------
    def _make_list(self) -> QListWidget:
        lst = QListWidget(self)
        lst.setIconSize(_PREVIEW_SIZE)
        lst.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        lst.itemDoubleClicked.connect(self._on_item_double_clicked)
        return lst

    def _current_kind(self) -> str:
        return "paragraph" if self._tabs.currentWidget() is self._paragraph_list else "character"

    def _current_list(self) -> QListWidget:
        return cast(QListWidget, self._tabs.currentWidget())

    def _styles_for(self, kind: str) -> list[Style]:
        if kind == "paragraph":
            return cast(list[Style], self._document.paragraph_styles)
        return cast(list[Style], self._document.character_styles)

    def _has_name(self, kind: str, name: str) -> bool:
        return any(s.name == name for s in self._styles_for(kind))

    def _find(self, kind: str, name: str) -> Style | None:
        if kind == "paragraph":
            return cast(Style | None, self._document.find_paragraph_style(name))
        return cast(Style | None, self._document.find_character_style(name))

    # ------------------------------------------------------------------
    # public refresh
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Rebuild both lists from the document's style registries."""
        for kind, list_widget in (
            ("paragraph", self._paragraph_list),
            ("character", self._character_list),
        ):
            styles = self._styles_for(kind)
            registry: dict[str, Style] = {s.name: s for s in styles}
            list_widget.clear()
            for style in sorted(styles, key=lambda s: s.name):
                pix = _render_preview(_resolved_font(registry, style.name))
                item = QListWidgetItem(QIcon(pix), style.name)
                item.setData(Qt.ItemDataRole.UserRole, style.name)
                list_widget.addItem(item)

    # ------------------------------------------------------------------
    # toolbar handlers
    # ------------------------------------------------------------------
    def _on_new(self) -> None:
        kind = self._current_kind()
        name, ok = QInputDialog.getText(self, "New style", "Style name:")
        if not ok or not name:
            return
        if self._has_name(kind, name):
            QMessageBox.warning(self, "Duplicate", f"{name!r} already exists.")
            return
        if kind == "paragraph":
            AddParagraphStyleCommand(self._cmd_doc, ParagraphStyle(name=name)).redo()
        else:
            AddCharacterStyleCommand(self._cmd_doc, CharacterStyle(name=name)).redo()
        self.refresh()

    def _on_duplicate(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        kind = self._current_kind()
        new_name, ok = QInputDialog.getText(
            self,
            "Duplicate style",
            "New name:",
            text=f"{name} copy",
        )
        if not ok or not new_name:
            return
        if self._has_name(kind, new_name):
            QMessageBox.warning(self, "Duplicate", f"{new_name!r} already exists.")
            return
        if kind == "paragraph":
            DuplicateParagraphStyleCommand(self._cmd_doc, name, new_name).redo()
        else:
            DuplicateCharacterStyleCommand(self._cmd_doc, name, new_name).redo()
        self.refresh()

    def _on_delete(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        kind = self._current_kind()
        confirm = QMessageBox.question(
            self,
            "Delete style",
            f"Delete {kind} style {name!r}?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if kind == "paragraph":
            DeleteParagraphStyleCommand(self._cmd_doc, name).redo()
        else:
            DeleteCharacterStyleCommand(self._cmd_doc, name).redo()
        self.refresh()

    def _on_edit(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        self._open_editor(name)

    def _on_apply(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        self._apply(name)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(name, str):
            self._apply(name)

    def _apply(self, name: str) -> None:
        if self._current_kind() == "paragraph":
            ApplyParagraphStyleCommand(self._cmd_doc, name).redo()
        else:
            ApplyCharacterStyleCommand(self._cmd_doc, name).redo()

    # ------------------------------------------------------------------
    # editor wiring
    # ------------------------------------------------------------------
    def _open_editor(self, name: str) -> None:
        kind = self._current_kind()
        style = self._find(kind, name)
        if style is None:
            return
        dialog = StyleEditorDialog(
            self._document,
            kind=kind,
            style=cast(ParagraphStyle | CharacterStyle, style),
            parent=self,
        )
        dialog.exec()
        self.refresh()

    def _selected_name(self) -> str | None:
        lst = self._current_list()
        items = lst.selectedItems()
        if not items:
            return None
        data = items[0].data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, str) else None


__all__ = ["StyleSheetsPalette"]
