"""Pages palette — thumbnails grid + master pages section.

Per spec §9: the right-side dock has a Pages tab that shows page thumbnails
(icon-mode list, drag-reorderable), a toolbar (New / Duplicate / Delete /
Move Up / Move Down / Master Page submenu), and a Master Pages section below.

Thumbnails regenerate on ``Document.page_changed`` (debounced 200 ms).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from PySide6.QtCore import (
    QAbstractListModel,
    QMimeData,
    QModelIndex,
    QPersistentModelIndex,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ._stubs import (
    AssignMasterCommand,
    Command,
    CommandBus,
    DeletePageCommand,
    Document,
    DuplicatePageCommand,
    MovePageCommand,
    NewPageCommand,
    Page,
    _CommandRecord,
)

THUMBNAIL_SIZE = QSize(96, 128)
DEBOUNCE_MS = 200


class PageThumbnailRenderer(Protocol):
    """Renders a thumbnail for a page.

    Real renderer (lands with unit #16 ``render-canvas``) will rasterize the
    actual page contents. This Protocol is the seam.
    """

    def render(self, page: Page, index: int, size: QSize) -> QPixmap: ...


class _DefaultThumbnailRenderer:
    """Stub renderer: white rectangle with the page number drawn on it."""

    def render(self, page: Page, index: int, size: QSize) -> QPixmap:
        pix = QPixmap(size)
        pix.fill(Qt.GlobalColor.white)
        painter = QPainter(pix)
        try:
            painter.setPen(Qt.GlobalColor.black)
            painter.drawRect(0, 0, size.width() - 1, size.height() - 1)
            painter.drawText(
                pix.rect(),
                Qt.AlignmentFlag.AlignCenter,
                str(index + 1),
            )
        finally:
            painter.end()
        return pix


class _PagesModel(QAbstractListModel):
    """List model backing the QListView of page thumbnails."""

    def __init__(
        self,
        doc: Document,
        renderer: PageThumbnailRenderer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doc = doc
        self._renderer = renderer

    # --- Qt model API ------------------------------------------------------
    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = QModelIndex(),  # noqa: B008
    ) -> int:
        if parent.isValid():
            return 0
        return len(self._doc.pages)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._doc.pages)):
            return None
        page = self._doc.pages[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"Page {index.row() + 1}"
        if role == Qt.ItemDataRole.DecorationRole:
            return QIcon(self._renderer.render(page, index.row(), THUMBNAIL_SIZE))
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"Page {index.row() + 1} · master={page.master_id or '—'}"
        return None

    def flags(
        self, index: QModelIndex | QPersistentModelIndex
    ) -> Qt.ItemFlag:
        base = super().flags(index)
        if index.isValid():
            return base | Qt.ItemFlag.ItemIsDragEnabled
        return base | Qt.ItemFlag.ItemIsDropEnabled

    def supportedDropActions(self) -> Qt.DropAction:
        return Qt.DropAction.MoveAction

    def mimeTypes(self) -> list[str]:
        return ["application/x-msword-pageindex"]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        mime = QMimeData()
        rows = sorted({i.row() for i in indexes if i.isValid()})
        if rows:
            mime.setData(
                "application/x-msword-pageindex",
                ",".join(str(r) for r in rows).encode("utf-8"),
            )
        return mime

    def reset_now(self) -> None:
        self.beginResetModel()
        self.endResetModel()


class PagesPalette(QWidget):
    """Pages palette widget: toolbar + thumbnail grid + master pages list."""

    page_selected = Signal(int)
    master_page_selected = Signal(str)

    def __init__(
        self,
        doc: Document,
        bus: CommandBus | None = None,
        renderer: PageThumbnailRenderer | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doc = doc
        self._bus = bus or CommandBus()
        self._renderer: PageThumbnailRenderer = renderer or _DefaultThumbnailRenderer()

        self._model = _PagesModel(doc, self._renderer, self)

        # debounced refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(DEBOUNCE_MS)
        self._refresh_timer.timeout.connect(self._do_refresh)

        self._build_ui()
        self._wire_signals()

    # ------------------------------------------------------------------ API
    @property
    def bus(self) -> CommandBus:
        return self._bus

    @property
    def view(self) -> QListView:
        return self._view

    # --------------------------------------------------------------- layout
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        # toolbar
        self._toolbar = QToolBar(self)
        self._act_new = QAction("New Page", self)
        self._act_new.triggered.connect(self._on_new_page)
        self._act_dup = QAction("Duplicate", self)
        self._act_dup.triggered.connect(self._on_duplicate)
        self._act_del = QAction("Delete", self)
        self._act_del.triggered.connect(self._on_delete)
        self._act_up = QAction("Move Up", self)
        self._act_up.triggered.connect(self._on_move_up)
        self._act_down = QAction("Move Down", self)
        self._act_down.triggered.connect(self._on_move_down)

        self._toolbar.addAction(self._act_new)
        self._toolbar.addAction(self._act_dup)
        self._toolbar.addAction(self._act_del)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._act_up)
        self._toolbar.addAction(self._act_down)

        # Master Page submenu (button on the toolbar)
        self._master_button = QToolButton(self)
        self._master_button.setText("Master Page")
        self._master_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._master_menu = QMenu(self._master_button)
        self._master_button.setMenu(self._master_menu)
        self._toolbar.addSeparator()
        self._toolbar.addWidget(self._master_button)
        self._refresh_master_menu()

        outer.addWidget(self._toolbar)

        # thumbnail list (icon mode)
        self._view = QListView(self)
        self._view.setModel(self._model)
        self._view.setViewMode(QListView.ViewMode.IconMode)
        self._view.setIconSize(THUMBNAIL_SIZE)
        self._view.setMovement(QListView.Movement.Snap)
        self._view.setResizeMode(QListView.ResizeMode.Adjust)
        self._view.setSpacing(6)
        self._view.setUniformItemSizes(True)
        self._view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._view.setDragEnabled(True)
        self._view.setAcceptDrops(True)
        self._view.setDropIndicatorShown(True)
        self._view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._view.setDefaultDropAction(Qt.DropAction.MoveAction)
        outer.addWidget(self._view, 1)

        # Master pages section
        master_header = QLabel("Master Pages", self)
        master_header.setStyleSheet("font-weight: bold; padding-top: 4px;")
        outer.addWidget(master_header)

        self._master_list = QListWidget(self)
        self._master_list.setMaximumHeight(96)
        outer.addWidget(self._master_list)
        self._refresh_master_list()

    # ------------------------------------------------------------ wiring
    def _wire_signals(self) -> None:
        self._doc.page_changed.connect(self._schedule_refresh)
        self._doc.changed.connect(self._schedule_refresh)
        self._view.clicked.connect(self._on_view_clicked)
        # drag-reorder hook: rowsMoved is emitted by the model after a move
        self._model.rowsMoved.connect(self._on_rows_moved)
        self._master_list.itemDoubleClicked.connect(self._on_master_dbl_clicked)

    # ------------------------------------------------------------ refresh
    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    def _do_refresh(self) -> None:
        self._model.reset_now()
        self._refresh_master_menu()
        self._refresh_master_list()

    def _refresh_master_menu(self) -> None:
        self._master_menu.clear()
        for master in self._doc.master_pages:
            act = QAction(master.name, self._master_menu)
            act.setData(master.id)
            act.triggered.connect(self._make_master_assign(master.id))
            self._master_menu.addAction(act)

    def _make_master_assign(self, master_id: str) -> Callable[[], None]:
        def _trigger() -> None:
            idx = self._current_row()
            if idx is None:
                return
            self._dispatch(AssignMasterCommand(page_index=idx, master_id=master_id))

        return _trigger

    def _refresh_master_list(self) -> None:
        self._master_list.clear()
        for master in self._doc.master_pages:
            item = QListWidgetItem(master.name)
            item.setData(Qt.ItemDataRole.UserRole, master.id)
            self._master_list.addItem(item)

    # ------------------------------------------------------------ slots
    def _current_row(self) -> int | None:
        idxs = self._view.selectionModel().selectedIndexes()
        if not idxs:
            return None
        return idxs[0].row()

    def _on_view_clicked(self, index: QModelIndex) -> None:
        if index.isValid():
            self.page_selected.emit(index.row())

    def _on_master_dbl_clicked(self, item: QListWidgetItem) -> None:
        master_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(master_id, str):
            self.master_page_selected.emit(master_id)

    def _on_new_page(self) -> None:
        idx = self._current_row()
        insert_at = (idx + 1) if idx is not None else None
        self._dispatch(NewPageCommand(page_id=_new_id("p"), index=insert_at))

    def _on_duplicate(self) -> None:
        idx = self._current_row()
        if idx is None:
            return
        self._dispatch(DuplicatePageCommand(index=idx, new_id=_new_id("p")))

    def _on_delete(self) -> None:
        idx = self._current_row()
        if idx is None:
            return
        self._dispatch(DeletePageCommand(index=idx))

    def _on_move_up(self) -> None:
        idx = self._current_row()
        if idx is None or idx == 0:
            return
        self._dispatch(MovePageCommand(src=idx, dst=idx - 1))

    def _on_move_down(self) -> None:
        idx = self._current_row()
        if idx is None or idx >= len(self._doc.pages) - 1:
            return
        self._dispatch(MovePageCommand(src=idx, dst=idx + 1))

    def _on_rows_moved(
        self,
        _parent: QModelIndex,
        start: int,
        _end: int,
        _dest: QModelIndex,
        row: int,
    ) -> None:
        # QAbstractItemModel.rowsMoved adjusts ``row`` for the removal already.
        dst = row if row < start else row - 1
        if dst != start:
            self._dispatch(MovePageCommand(src=start, dst=dst))

    # ------------------------------------------------------------ dispatch
    def _dispatch(self, cmd: Command) -> None:
        # apply locally (the real undo stack will do this) and notify the bus
        cmd.apply(self._doc)
        self._bus.dispatch(_CommandRecord(name=cmd.name, args=(cmd,)))


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
