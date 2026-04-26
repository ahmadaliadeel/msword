"""Vertical tools palette (Quark-style icon strip).

Per spec §9: a vertical icon strip on the left (`QToolBar` in
`Qt.LeftToolBarArea`) with one toggleable action per tool, exclusive within
itself. Toggling an action sets the selected tool on the active canvas via
``canvas.set_tool(tool)``.

Tools provided by this unit, in palette order:

  1. Selection
  2. Item Mover
  3. Text Frame
  4. Picture Frame
  5. Rectangle
  6. Oval
  7. Polygon
  8. Pen
  9. Line
 10. Hand
 11. Zoom

Table & Linker/Unlinker tools land in unit 21 and append to this palette.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QStyle, QToolBar

from msword.ui.tools import (
    HandTool,
    ItemMoverTool,
    LineTool,
    OvalTool,
    PenTool,
    PictureFrameTool,
    PolygonTool,
    RectTool,
    SelectionTool,
    TextFrameTool,
    Tool,
    ZoomTool,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

    from msword.ui.tools.base import CanvasLike


#: Default tool order, top-to-bottom on the palette.
DEFAULT_TOOL_TYPES: tuple[type[Tool], ...] = (
    SelectionTool,
    ItemMoverTool,
    TextFrameTool,
    PictureFrameTool,
    RectTool,
    OvalTool,
    PolygonTool,
    PenTool,
    LineTool,
    HandTool,
    ZoomTool,
)


#: Fallback Qt standard pixmaps for each tool type. The real icon resources
#: arrive with the asset/branding pass; until then these keep the palette
#: visually distinct without requiring artwork.
_FALLBACK_ICONS: dict[type[Tool], QStyle.StandardPixmap] = {
    SelectionTool: QStyle.StandardPixmap.SP_ArrowRight,
    ItemMoverTool: QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton,
    TextFrameTool: QStyle.StandardPixmap.SP_FileDialogDetailedView,
    PictureFrameTool: QStyle.StandardPixmap.SP_FileIcon,
    RectTool: QStyle.StandardPixmap.SP_TitleBarMaxButton,
    OvalTool: QStyle.StandardPixmap.SP_DialogResetButton,
    PolygonTool: QStyle.StandardPixmap.SP_FileDialogContentsView,
    PenTool: QStyle.StandardPixmap.SP_DialogApplyButton,
    LineTool: QStyle.StandardPixmap.SP_ToolBarVerticalExtensionButton,
    HandTool: QStyle.StandardPixmap.SP_DialogOpenButton,
    ZoomTool: QStyle.StandardPixmap.SP_FileDialogContentsView,
}


class ToolsPalette(QToolBar):
    """Vertical, exclusive-action toolbar that drives the active canvas tool."""

    def __init__(
        self,
        canvas: CanvasLike | None = None,
        parent: QWidget | None = None,
        *,
        tool_types: Iterable[type[Tool]] | None = None,
    ) -> None:
        super().__init__("Tools", parent)
        self.setObjectName("ToolsPalette")
        self.setOrientation(Qt.Orientation.Vertical)
        self.setMovable(False)
        self.setFloatable(False)
        self.setAllowedAreas(Qt.ToolBarArea.LeftToolBarArea)

        self._canvas: CanvasLike | None = canvas
        self._group = QActionGroup(self)
        self._group.setExclusive(True)
        self._tools: list[Tool] = []
        self._actions: list[QAction] = []

        types = tuple(tool_types) if tool_types is not None else DEFAULT_TOOL_TYPES
        for tool_type in types:
            self._add_tool(tool_type())

        if self._actions:
            self._actions[0].setChecked(True)
            self._on_action_triggered(self._actions[0])

    @property
    def tools(self) -> list[Tool]:
        return list(self._tools)

    @property
    def actions_in_order(self) -> list[QAction]:
        return list(self._actions)

    def set_canvas(self, canvas: CanvasLike | None) -> None:
        """Bind/unbind the canvas the palette drives."""
        self._canvas = canvas
        if canvas is None:
            return
        for action in self._actions:
            if action.isChecked():
                self._activate_action_tool(action)
                return

    def _add_tool(self, tool: Tool) -> None:
        action = QAction(self._icon_for(tool), tool.name, self)
        action.setCheckable(True)
        action.setToolTip(tool.name)
        action.setData(tool)
        action.triggered.connect(lambda _checked=False, a=action: self._on_action_triggered(a))
        self._group.addAction(action)
        self.addAction(action)
        self._tools.append(tool)
        self._actions.append(action)

    def _icon_for(self, tool: Tool) -> QIcon:
        themed = QIcon.fromTheme(tool.icon_name) if tool.icon_name else QIcon()
        if not themed.isNull():
            return themed
        pixmap = _FALLBACK_ICONS.get(type(tool))
        if pixmap is None:
            return QIcon()
        return self.style().standardIcon(pixmap)

    def _on_action_triggered(self, action: QAction) -> None:
        if not action.isChecked():
            # Exclusive group means another action will fire its own triggered;
            # don't deactivate here or we'd race with the activator.
            return
        self._activate_action_tool(action)

    def _activate_action_tool(self, action: QAction) -> None:
        tool = action.data()
        canvas = self._canvas
        if canvas is None or tool is None:
            return
        canvas.set_tool(tool)
