# mypy: disable-error-code="call-arg, attr-defined, arg-type, assignment, no-any-return, union-attr"
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
from msword.model.document import Document
from msword.model.style import (
    CharacterStyle,
    ParagraphStyle,
    StyleResolver,
)
from msword.ui.palettes._style_editor_dialog import StyleEditorDialog

_PREVIEW_TEXT = "Aa Bb Cc 123"
_PREVIEW_SIZE = QSize(160, 28)


def _resolved_font(
    styles: dict[str, ParagraphStyle] | dict[str, CharacterStyle],
    name: str,
) -> QFont:
    """Resolve a style's typographic properties up the based-on chain
    and produce a :class:`QFont` for the row preview. Falls back to
    sensible defaults so the preview is always readable.
    """
    family = StyleResolver.resolve(styles, name, "font_family") or "Sans Serif"
    size = StyleResolver.resolve(styles, name, "font_size") or 12.0
    font = QFont(str(family))
    font.setPointSizeF(float(size))
    bold = StyleResolver.resolve(styles, name, "bold")
    italic = StyleResolver.resolve(styles, name, "italic")
    underline = StyleResolver.resolve(styles, name, "underline")
    if bold:
        font.setBold(True)
    if italic:
        font.setItalic(True)
    if underline:
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
        # vertically center on baseline
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

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar — New / Duplicate / Delete / Edit / Apply
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

    def _registry_for(
        self, kind: str
    ) -> Any:  # dict on unit-25's stub Document, list on master — caller treats both
        return (
            self._document.paragraph_styles
            if kind == "paragraph"
            else self._document.character_styles
        )

    # ------------------------------------------------------------------
    # public refresh
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Rebuild both lists from the document's style registries."""
        self._paragraph_list.clear()
        for name in sorted(self._document.paragraph_styles):
            self._paragraph_list.addItem(self._make_item("paragraph", name))
        self._character_list.clear()
        for name in sorted(self._document.character_styles):
            self._character_list.addItem(self._make_item("character", name))

    def _make_item(self, kind: str, name: str) -> QListWidgetItem:
        registry = self._registry_for(kind)
        font = _resolved_font(registry, name)
        pix = _render_preview(font)
        item = QListWidgetItem(QIcon(pix), name)
        item.setData(Qt.ItemDataRole.UserRole, name)
        return item

    # ------------------------------------------------------------------
    # toolbar handlers
    # ------------------------------------------------------------------
    def _on_new(self) -> None:
        kind = self._current_kind()
        name, ok = QInputDialog.getText(self, "New style", "Style name:")
        if not ok or not name:
            return
        registry = self._registry_for(kind)
        if name in registry:
            QMessageBox.warning(self, "Duplicate", f"{name!r} already exists.")
            return
        cmd: AddParagraphStyleCommand | AddCharacterStyleCommand
        if kind == "paragraph":
            cmd = AddParagraphStyleCommand(self._document, ParagraphStyle(name=name))
        else:
            cmd = AddCharacterStyleCommand(self._document, CharacterStyle(name=name))
        cmd.redo()
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
        if new_name in self._registry_for(kind):
            QMessageBox.warning(self, "Duplicate", f"{new_name!r} already exists.")
            return
        dup_cmd: DuplicateParagraphStyleCommand | DuplicateCharacterStyleCommand
        if kind == "paragraph":
            dup_cmd = DuplicateParagraphStyleCommand(self._document, name, new_name)
        else:
            dup_cmd = DuplicateCharacterStyleCommand(self._document, name, new_name)
        dup_cmd.redo()
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
            DeleteParagraphStyleCommand(self._document, name).redo()
        else:
            DeleteCharacterStyleCommand(self._document, name).redo()
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
            ApplyParagraphStyleCommand(self._document, name).redo()
        else:
            ApplyCharacterStyleCommand(self._document, name).redo()

    # ------------------------------------------------------------------
    # editor wiring
    # ------------------------------------------------------------------
    def _open_editor(self, name: str) -> None:
        kind = self._current_kind()
        registry = self._registry_for(kind)
        style = registry[name]
        dialog = StyleEditorDialog(
            self._document,
            kind=kind,
            style=style,
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
