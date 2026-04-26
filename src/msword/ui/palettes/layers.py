"""Layers palette dock widget.

Owned by unit #24 (`ui-layers-palette`).

This module:

* defines the `LayersPalette` `QDockWidget` (per-page layer list, eye /
  lock toggles, color swatch, drag-reorder, toolbar with New / Delete /
  Duplicate);
* defines lightweight `Command` classes for the layer mutations the
  palette emits (`SetLayerVisibilityCommand`, `SetLayerLockCommand`,
  `ReorderLayersCommand`). These are deliberately self-contained so this
  unit lands without depending on the (sibling) commands unit; once that
  unit lands they will be replaced by / reduce to thin re-exports.

The palette accesses the document via a small `Protocol` so it does not
need to import the (sibling) `Document` / `Page` modules.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from PySide6.QtCore import (
    QAbstractItemModel,
    QByteArray,
    QMimeData,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QStyledItemDelegate,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from msword.model.layer import Layer

# A single shared invalid index reused as the default for the read-only
# tree-model accessors. Re-using one instance avoids ruff B008 (function
# calls in argument defaults) and matches the QAbstractItemModel idiom of
# treating an invalid index as "the root".
_NO_PARENT = QModelIndex()

# ---------------------------------------------------------------------------
# Protocols — minimal stub shape we need from the document side. The real
# `Document` / `Page` (owned by other units) need only satisfy these.
# ---------------------------------------------------------------------------


@runtime_checkable
class _PageLike(Protocol):
    """Anything with a mutable `layers` list of `Layer`."""

    layers: list[Layer]


@runtime_checkable
class _UndoStackLike(Protocol):
    def push(self, command: object) -> None: ...


class _SignalLike(Protocol):
    """Anything with the `Signal` connect / disconnect / emit shape.

    PySide6 signals are instances of `SignalInstance` at runtime, which
    mypy cannot infer through the class-level `Signal()` declaration; we
    therefore type the protocol attributes structurally.
    """

    def connect(self, slot: Any, /) -> Any: ...

    def disconnect(self, slot: Any, /) -> Any: ...

    def emit(self, *args: Any) -> None: ...


@runtime_checkable
class _DocumentLike(Protocol):
    """Minimum shape the palette needs from a Document.

    Real documents will provide a richer API; this Protocol pins down
    only the seams the palette touches.
    """

    current_page_changed: _SignalLike
    layers_changed: _SignalLike

    @property
    def current_page(self) -> _PageLike | None: ...

    @property
    def undo_stack(self) -> _UndoStackLike: ...


# ---------------------------------------------------------------------------
# Commands — self-contained in this unit; the commands unit will absorb
# them later. Each is intentionally small: __init__ captures the inputs,
# `redo()` applies, `undo()` reverses. They expose a `text()` for the
# undo stack, matching the QUndoCommand convention.
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SetLayerVisibilityCommand:
    page: _PageLike
    layer_id: str
    visible: bool
    _previous: bool = False

    def text(self) -> str:
        return "Toggle layer visibility"

    def redo(self) -> None:
        layer = _find_layer(self.page, self.layer_id)
        self._previous = layer.visible
        layer.visible = self.visible

    def undo(self) -> None:
        _find_layer(self.page, self.layer_id).visible = self._previous


@dataclass(slots=True)
class SetLayerLockCommand:
    page: _PageLike
    layer_id: str
    locked: bool
    _previous: bool = False

    def text(self) -> str:
        return "Toggle layer lock"

    def redo(self) -> None:
        layer = _find_layer(self.page, self.layer_id)
        self._previous = layer.locked
        layer.locked = self.locked

    def undo(self) -> None:
        _find_layer(self.page, self.layer_id).locked = self._previous


@dataclass(slots=True)
class ReorderLayersCommand:
    """Reorder the page's layer list to the given order of layer ids.

    `order` is the new top-to-bottom (palette order) sequence of layer
    ids. We translate that to per-layer `z_order` values (highest at the
    top of the palette = highest z_order) and also resort the page's
    `layers` list to match — readers may rely on either.
    """

    page: _PageLike
    order: list[str]
    _previous_order: list[str] | None = None

    def text(self) -> str:
        return "Reorder layers"

    def redo(self) -> None:
        self._previous_order = [layer.id for layer in self.page.layers]
        _apply_layer_order(self.page, self.order)

    def undo(self) -> None:
        if self._previous_order is not None:
            _apply_layer_order(self.page, self._previous_order)


def _find_layer(page: _PageLike, layer_id: str) -> Layer:
    for layer in page.layers:
        if layer.id == layer_id:
            return layer
    raise KeyError(f"layer {layer_id!r} not found on page")


def _apply_layer_order(page: _PageLike, order: list[str]) -> None:
    by_id = {layer.id: layer for layer in page.layers}
    new_layers = [by_id[layer_id] for layer_id in order if layer_id in by_id]
    # Append any layers that weren't in `order` (defensive — should not
    # happen via the palette but keeps the model from losing data).
    for layer in page.layers:
        if layer.id not in order:
            new_layers.append(layer)
    # Top of palette (index 0) is highest z_order.
    total = len(new_layers)
    for index, layer in enumerate(new_layers):
        layer.z_order = total - 1 - index
    page.layers[:] = new_layers


# ---------------------------------------------------------------------------
# Item model
# ---------------------------------------------------------------------------


COL_VISIBLE = 0
COL_LOCK = 1
COL_SWATCH = 2
COL_NAME = 3
_COLUMN_COUNT = 4

_LAYERS_MIME = "application/x-msword-layer-ids"


class LayersTreeModel(QAbstractItemModel):
    """Flat tree model exposing a page's layers, top = highest z_order."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._page: _PageLike | None = None

    # --- page binding ----------------------------------------------------

    def set_page(self, page: _PageLike | None) -> None:
        self.beginResetModel()
        self._page = page
        self.endResetModel()

    def page(self) -> _PageLike | None:
        return self._page

    def _layers(self) -> list[Layer]:
        # Returned list is read-only-by-convention; the model never mutates it
        # so we hand back the page's own list to avoid a per-call copy.
        return self._page.layers if self._page is not None else []

    def layer_at(self, row: int) -> Layer | None:
        layers = self._layers()
        if 0 <= row < len(layers):
            return layers[row]
        return None

    # --- structure -------------------------------------------------------

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = _NO_PARENT) -> int:
        if parent.isValid():
            return 0
        return len(self._layers())

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = _NO_PARENT) -> int:
        return _COLUMN_COUNT

    def index(
        self,
        row: int,
        column: int,
        parent: QModelIndex | QPersistentModelIndex = _NO_PARENT,
    ) -> QModelIndex:
        if parent.isValid() or not (0 <= row < len(self._layers())):
            return QModelIndex()
        if not (0 <= column < _COLUMN_COUNT):
            return QModelIndex()
        return self.createIndex(row, column)

    def parent(  # type: ignore[override]
        self, child: QModelIndex | QPersistentModelIndex = _NO_PARENT
    ) -> QModelIndex:
        return QModelIndex()

    # --- data ------------------------------------------------------------

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid():
            return None
        layer = self.layer_at(index.row())
        if layer is None:
            return None
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == COL_NAME:
                return layer.name
            return None
        if role == Qt.ItemDataRole.DecorationRole:
            if column == COL_VISIBLE:
                return _eye_icon(layer.visible)
            if column == COL_LOCK:
                return _lock_icon(layer.locked)
            if column == COL_SWATCH:
                return _swatch_icon(layer.color)
            return None
        if role == Qt.ItemDataRole.ToolTipRole:
            if column == COL_VISIBLE:
                return "Visible" if layer.visible else "Hidden"
            if column == COL_LOCK:
                return "Locked" if layer.locked else "Unlocked"
            if column == COL_NAME:
                return layer.name
        if role == Qt.ItemDataRole.UserRole:
            return layer.id
        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if (
            orientation != Qt.Orientation.Horizontal
            or role != Qt.ItemDataRole.DisplayRole
        ):
            return None
        return {
            COL_VISIBLE: "",
            COL_LOCK: "",
            COL_SWATCH: "",
            COL_NAME: "Name",
        }.get(section, "")

    def flags(
        self, index: QModelIndex | QPersistentModelIndex
    ) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemNeverHasChildren
        )

    # --- drag & drop -----------------------------------------------------
    #
    # We don't actually mutate the layer list here — the view captures the
    # drop and emits a `ReorderLayersCommand` via the palette. But we must
    # advertise drag/drop support so QTreeView fires `dropEvent`.

    def supportedDragActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:
        return [_LAYERS_MIME]

    def mimeData(  # type: ignore[override]
        self, indexes: list[QModelIndex] | list[QPersistentModelIndex]
    ) -> QMimeData | None:
        rows: list[int] = []
        for idx in indexes:
            if idx.isValid() and idx.row() not in rows:
                rows.append(idx.row())
        ids: list[str] = []
        for row in rows:
            layer = self.layer_at(row)
            if layer is not None:
                ids.append(layer.id)
        if not ids:
            return None
        data = QMimeData()
        data.setData(_LAYERS_MIME, QByteArray("\n".join(ids).encode("utf-8")))
        return data


# ---------------------------------------------------------------------------
# Icons / swatch helpers
# ---------------------------------------------------------------------------


# Icons are returned to Qt for every visible row on every paint, so we
# memoize them by their inputs. Eye / lock have two values each; swatch
# is keyed by the RGB triple (typical layer count is single digits).
_ICON_SIZE = 14
_ICON_FG = "#222"
_ICON_DIM = "#aaa"
_eye_icon_cache: dict[bool, QIcon] = {}
_lock_icon_cache: dict[bool, QIcon] = {}
_swatch_icon_cache: dict[tuple[int, int, int], QIcon] = {}


def _swatch_icon(color: tuple[int, int, int]) -> QIcon:
    cached = _swatch_icon_cache.get(color)
    if cached is not None:
        return cached
    pix = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pix.fill(QColor(*color))
    icon = QIcon(pix)
    _swatch_icon_cache[color] = icon
    return icon


def _eye_icon(visible: bool) -> QIcon:
    cached = _eye_icon_cache.get(visible)
    if cached is not None:
        return cached
    pix = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(_ICON_FG if visible else _ICON_DIM))
    painter.drawEllipse(2, 4, 10, 6)
    if visible:
        painter.setBrush(QColor(_ICON_FG))
        painter.drawEllipse(5, 5, 4, 4)
    painter.end()
    icon = QIcon(pix)
    _eye_icon_cache[visible] = icon
    return icon


def _lock_icon(locked: bool) -> QIcon:
    cached = _lock_icon_cache.get(locked)
    if cached is not None:
        return cached
    pix = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor(_ICON_FG if locked else _ICON_DIM))
    painter.drawRect(3, 6, 8, 6)
    painter.drawArc(4, 2, 6, 8, 0, 180 * 16)
    painter.end()
    icon = QIcon(pix)
    _lock_icon_cache[locked] = icon
    return icon


# ---------------------------------------------------------------------------
# Tree view: catches click on visibility / lock columns and the drop event.
# ---------------------------------------------------------------------------


class _LayersTreeView(QTreeView):
    """Tree view that translates user gestures into command requests.

    Column clicks (visibility, lock) and drop reorders are surfaced via
    callbacks rather than direct command pushes so the palette stays
    the single place that talks to the undo stack.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setUniformRowHeights(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setItemDelegate(QStyledItemDelegate(self))
        self._on_toggle_visibility: Callable[[str], None] | None = None
        self._on_toggle_lock: Callable[[str], None] | None = None
        self._on_reorder: Callable[[list[str]], None] | None = None

    def set_callbacks(
        self,
        toggle_visibility: Callable[[str], None],
        toggle_lock: Callable[[str], None],
        reorder: Callable[[list[str]], None],
    ) -> None:
        self._on_toggle_visibility = toggle_visibility
        self._on_toggle_lock = toggle_lock
        self._on_reorder = reorder

    # -- click toggles ----------------------------------------------------

    def mousePressEvent(self, event):  # type: ignore[no-untyped-def]
        index = self.indexAt(event.position().toPoint())
        if index.isValid():
            column = index.column()
            model = self.model()
            if isinstance(model, LayersTreeModel) and column in (
                COL_VISIBLE,
                COL_LOCK,
            ):
                layer = model.layer_at(index.row())
                if layer is not None:
                    if column == COL_VISIBLE and self._on_toggle_visibility:
                        self._on_toggle_visibility(layer.id)
                    elif column == COL_LOCK and self._on_toggle_lock:
                        self._on_toggle_lock(layer.id)
                    event.accept()
                    return
        super().mousePressEvent(event)

    # -- drop = reorder ---------------------------------------------------

    def dropEvent(self, event):  # type: ignore[no-untyped-def]
        model = self.model()
        if not isinstance(model, LayersTreeModel):
            super().dropEvent(event)
            return
        page = model.page()
        if page is None:
            event.ignore()
            return
        mime = event.mimeData()
        raw = mime.data(_LAYERS_MIME)
        if raw.isEmpty():
            super().dropEvent(event)
            return
        moving_ids = bytes(raw.data()).decode("utf-8").splitlines()
        moving_ids = [layer_id for layer_id in moving_ids if layer_id]
        if not moving_ids:
            event.ignore()
            return
        drop_row = self._target_row(event)
        current_ids = [layer.id for layer in page.layers]
        new_order = _compute_reorder(current_ids, moving_ids, drop_row)
        if new_order == current_ids:
            event.ignore()
            return
        if self._on_reorder is not None:
            self._on_reorder(new_order)
        # The palette will re-bind the model after the command is pushed,
        # so we accept-but-don't-let-Qt-mutate.
        event.accept()

    def _target_row(self, event) -> int:  # type: ignore[no-untyped-def]
        pos = event.position().toPoint()
        index = self.indexAt(pos)
        model = self.model()
        if not isinstance(model, LayersTreeModel):
            return 0
        if not index.isValid():
            return model.rowCount()
        rect = self.visualRect(index)
        # Drop in the lower half of the row → insert below it.
        if pos.y() >= rect.center().y():
            return index.row() + 1
        return index.row()


def _compute_reorder(
    current_ids: list[str], moving_ids: list[str], drop_row: int
) -> list[str]:
    moving_set = set(moving_ids)
    moving_in_order = [layer_id for layer_id in current_ids if layer_id in moving_set]
    remaining = [layer_id for layer_id in current_ids if layer_id not in moving_set]
    # Translate drop_row (in current_ids coordinates) into an index inside
    # `remaining` by counting how many non-moving rows precede it.
    insert_at = sum(
        1 for layer_id in current_ids[:drop_row] if layer_id not in moving_set
    )
    return remaining[:insert_at] + moving_in_order + remaining[insert_at:]


# ---------------------------------------------------------------------------
# Palette dock widget
# ---------------------------------------------------------------------------


class LayersPalette(QDockWidget):
    """Right-side dock palette listing the current page's layers.

    Construct with a document-like object that exposes
    `current_page_changed` (Qt signal), `current_page` (property), and
    `undo_stack` (with `push()`). The palette refreshes whenever the
    document signals a page change.
    """

    def __init__(
        self,
        document: _DocumentLike | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Layers", parent)
        self.setObjectName("LayersPalette")
        self._document: _DocumentLike | None = None

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QToolBar(container)
        toolbar.setIconSize(toolbar.iconSize())
        self._action_new = toolbar.addAction("New")
        self._action_delete = toolbar.addAction("Delete")
        self._action_duplicate = toolbar.addAction("Duplicate")
        self._action_new.setToolTip("New layer")
        self._action_delete.setToolTip("Delete selected layer")
        self._action_duplicate.setToolTip("Duplicate selected layer")
        layout.addWidget(toolbar)

        self._model = LayersTreeModel(self)
        self._tree = _LayersTreeView(container)
        self._tree.setModel(self._model)
        self._tree.set_callbacks(
            toggle_visibility=self._toggle_visibility,
            toggle_lock=self._toggle_lock,
            reorder=self._reorder,
        )
        layout.addWidget(self._tree, 1)

        self.setWidget(container)
        self._toolbar = toolbar

        if document is not None:
            self.set_document(document)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_document(self, document: _DocumentLike | None) -> None:
        if self._document is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self._document.current_page_changed.disconnect(self._refresh)
            with contextlib.suppress(RuntimeError, TypeError, AttributeError):
                self._document.layers_changed.disconnect(self._refresh)
        self._document = document
        if document is not None:
            document.current_page_changed.connect(self._refresh)
            # `layers_changed` is optional; subscribe defensively.
            layers_changed = getattr(document, "layers_changed", None)
            if layers_changed is not None and hasattr(layers_changed, "connect"):
                layers_changed.connect(self._refresh)
        self._refresh()

    def tree_view(self) -> QTreeView:
        return self._tree

    def model(self) -> LayersTreeModel:
        return self._model

    def toolbar(self) -> QToolBar:
        return self._toolbar

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _current_page(self) -> _PageLike | None:
        if self._document is None:
            return None
        return self._document.current_page

    def _refresh(self, *_args: object) -> None:
        self._model.set_page(self._current_page())

    def _push(self, command: object) -> None:
        if self._document is None:
            return
        self._document.undo_stack.push(command)
        self._refresh()

    def _toggle_visibility(self, layer_id: str) -> None:
        page = self._current_page()
        if page is None:
            return
        layer = _find_layer(page, layer_id)
        self._push(
            SetLayerVisibilityCommand(
                page=page, layer_id=layer_id, visible=not layer.visible
            )
        )

    def _toggle_lock(self, layer_id: str) -> None:
        page = self._current_page()
        if page is None:
            return
        layer = _find_layer(page, layer_id)
        self._push(
            SetLayerLockCommand(page=page, layer_id=layer_id, locked=not layer.locked)
        )

    def _reorder(self, new_order: list[str]) -> None:
        page = self._current_page()
        if page is None:
            return
        self._push(ReorderLayersCommand(page=page, order=new_order))


__all__ = [
    "LayersPalette",
    "LayersTreeModel",
    "ReorderLayersCommand",
    "SetLayerLockCommand",
    "SetLayerVisibilityCommand",
]
