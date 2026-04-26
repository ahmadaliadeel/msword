"""`PageItem` — one per page; renders chrome and parents the frame items.

Per spec §6 the chrome consists of:

- white page rect (the trim box);
- bleed (red dashed) — outer to the trim;
- margins (blue dashed) — inner to the trim;
- columns (purple dashed) — vertical guides inside the type area;
- baseline grid (cyan dotted) — horizontal hairlines on the leading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem

if TYPE_CHECKING:
    from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget

    from msword.ui.canvas._stubs import Page


_PAGE_FILL = QColor("#ffffff")
_PAGE_EDGE = QColor("#a0a0a0")
_BLEED_PEN = QColor("#d83a3a")
_MARGIN_PEN = QColor("#3478d8")
_COLUMN_PEN = QColor("#8b3ad8")
_BASELINE_PEN = QColor("#3ad8c8")


class PageItem(QGraphicsItem):
    """A single page rendered as a `QGraphicsItem`.

    Geometry is in scene units == points (1/72 inch). The item is positioned
    by the view (paged-mode strips them vertically; flow-mode stacks them
    contiguously with no inter-page gap).
    """

    def __init__(self, page: Page, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self._page = page
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, False)
        # Pages are non-interactive backgrounds; frames sit on top.
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(-1000)

    @property
    def page(self) -> Page:
        return self._page

    # -- QGraphicsItem ------------------------------------------------------

    def boundingRect(self) -> QRectF:
        bleed = self._page.bleed
        return QRectF(
            -bleed,
            -bleed,
            self._page.width + 2 * bleed,
            self._page.height + 2 * bleed,
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        page = self._page
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Page rect (white fill + faint edge).
        page_rect = QRectF(0.0, 0.0, page.width, page.height)
        painter.setPen(QPen(_PAGE_EDGE, 0.0))
        painter.setBrush(QBrush(_PAGE_FILL))
        painter.drawRect(page_rect)

        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Bleed (red dashed) — outside trim.
        if page.bleed > 0:
            pen = QPen(_BLEED_PEN, 0.0, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(
                QRectF(
                    -page.bleed,
                    -page.bleed,
                    page.width + 2 * page.bleed,
                    page.height + 2 * page.bleed,
                )
            )

        # Margins (blue dashed) — type area.
        margin_rect = QRectF(
            page.margin_left,
            page.margin_top,
            page.width - page.margin_left - page.margin_right,
            page.height - page.margin_top - page.margin_bottom,
        )
        if margin_rect.width() > 0 and margin_rect.height() > 0:
            pen = QPen(_MARGIN_PEN, 0.0, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(margin_rect)

            # Columns (purple dashed) — interior verticals.
            cols = max(1, page.column_count)
            if cols > 1:
                pen = QPen(_COLUMN_PEN, 0.0, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                column_w = (
                    margin_rect.width() - page.column_gutter * (cols - 1)
                ) / cols
                for i in range(1, cols):
                    x_left = margin_rect.left() + i * column_w + (i - 1) * page.column_gutter
                    x_right = x_left + page.column_gutter
                    painter.drawLine(
                        QPointF(x_left, margin_rect.top()),
                        QPointF(x_left, margin_rect.bottom()),
                    )
                    painter.drawLine(
                        QPointF(x_right, margin_rect.top()),
                        QPointF(x_right, margin_rect.bottom()),
                    )

        # Baseline grid (cyan dotted) — horizontal hairlines.
        if page.show_baseline_grid and page.baseline_grid > 0:
            pen = QPen(_BASELINE_PEN, 0.0, Qt.PenStyle.DotLine)
            painter.setPen(pen)
            y = page.margin_top + page.baseline_grid
            grid_left = page.margin_left
            grid_right = page.width - page.margin_right
            grid_bottom = page.height - page.margin_bottom
            while y < grid_bottom:
                painter.drawLine(QPointF(grid_left, y), QPointF(grid_right, y))
                y += page.baseline_grid
