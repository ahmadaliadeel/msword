"""Picture-frame tool: drag → empty ImageFrame; Shift opens a file dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog

from msword.ui.tools._drag_frame import DragRectFrameTool

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent


class PictureFrameTool(DragRectFrameTool):
    """Drag a rect → ``AddFrameCommand`` of kind ``"image"``.

    Holding Shift on release opens a file-picker so the user can populate the
    image source in the same gesture (the resulting path is forwarded to
    ``AddFrameCommand`` as ``image_path``).
    """

    name = "Picture Frame"
    icon_name = "tool-picture-frame"
    kind = "image"

    def _command_extra(self, event: QMouseEvent) -> dict[str, Any]:
        extra = super()._command_extra(event)
        if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            return extra
        path = self._prompt_for_image()
        if path:
            extra["image_path"] = path
        return extra

    def _prompt_for_image(self) -> str:
        """Open a file dialog. Overridable in tests."""
        path, _ = QFileDialog.getOpenFileName(
            None,
            "Select image",
            "",
            "Images (*.png *.jpg *.jpeg *.svg *.tif *.tiff)",
        )
        return path
