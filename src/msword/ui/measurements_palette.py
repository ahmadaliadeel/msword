"""Context-aware measurements palette (unit-22, spec §9).

A single non-detachable horizontal row that lives directly below the menu bar.
The visible widgets switch based on the current `Document.selection`:

* **Empty selection** — zoom + view-mode pickers only.
* **Frame selected** — geometry: X / Y / W / H / rotation / skew / aspect-lock.
* **Caret in text** — font / size / leading / tracking / alignment /
  Bold / Italic / Underline / Strike / paragraph-style / OpenType features.
* **Text frame selected without caret** — column count / gutter /
  vertical-align / baseline-grid override.

Numeric / continuous edits (spin boxes, font, view-mode) are pushed as
`Command`s on the document's `UndoStack` after a 250 ms debounce so that rapid
increments coalesce into a single undoable step. Discrete toggles (Bold,
Italic, OpenType features, baseline grid, …) push immediately.
"""

# mypy: disable-error-code="call-arg, attr-defined"
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QWidget,
)

from msword.commands import (
    Command,
    MoveFrameCommand,
    ResizeFrameCommand,
    RotateFrameCommand,
    SetAlignmentCommand,
    SetAspectLockCommand,
    SetBaselineGridCommand,
    SetBoldCommand,
    SetColumnsCommand,
    SetFontCommand,
    SetGutterCommand,
    SetItalicCommand,
    SetLeadingCommand,
    SetOpenTypeFeatureCommand,
    SetParagraphStyleCommand,
    SetSizeCommand,
    SetStrikeCommand,
    SetTrackingCommand,
    SetUnderlineCommand,
    SetVerticalAlignCommand,
    SetViewModeCommand,
    SetZoomCommand,
    SkewFrameCommand,
)
from msword.model.frame import Frame, TextFrame

if TYPE_CHECKING:
    from msword.model.document import Document


# Mode constants for the mode stack.
_MODE_EMPTY = 0
_MODE_GEOMETRY = 1
_MODE_TEXT = 2
_MODE_COLUMNS = 3

# Edits debounce before pushing a Command (per spec §9 / unit-22 task brief).
DEBOUNCE_MS = 250

# Placeholder shown in numeric fields when the selection contains conflicting
# values (multi-frame select, mixed runs, …). Quark / InDesign use an em-dash.
MIXED_PLACEHOLDER = "—"

# OpenType feature tags surfaced in the popup. Stylistic-set / character-variant
# tags are listed in the spec §9 / §5.
_OT_FEATURES: tuple[tuple[str, str], ...] = (
    ("liga", "Standard Ligatures"),
    ("dlig", "Discretionary Ligatures"),
    ("smcp", "Small Caps"),
    *((f"ss{i:02d}", f"Stylistic Set {i:02d}") for i in range(1, 21)),
)


class MeasurementsPalette(QWidget):
    """Single-row, context-aware top palette.

    Construct with the `Document` whose state should drive it. The palette
    subscribes to `selection_changed` and `caret_changed`, switches mode
    automatically, and pushes typed commands onto `document.undo_stack`.
    """

    def __init__(self, document: Document, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = document
        self._suspend_signals = False  # set while we re-populate widgets

        # Pending command, waiting for the debounce timer to fire.
        self._pending_command: Command | None = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(DEBOUNCE_MS)
        self._debounce.timeout.connect(self._flush_pending)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(6, 2, 6, 2)
        outer.setSpacing(8)

        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._build_empty_mode())
        self._stack.addWidget(self._build_geometry_mode())
        self._stack.addWidget(self._build_text_mode())
        self._stack.addWidget(self._build_columns_mode())
        outer.addWidget(self._stack)
        outer.addStretch(1)

        # Subscribe to selection / caret events when the document exposes them
        # (units 2-9 may not have wired these signals yet on master).
        for sig_name in ("selection_changed", "caret_changed"):
            sig = getattr(document, sig_name, None)
            if sig is not None and hasattr(sig, "connect"):
                sig.connect(self._refresh)
        self._refresh()

    # ------------------------------------------------------------------ build

    def _build_empty_mode(self) -> QWidget:
        page = QWidget(self)
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        row.addWidget(QLabel("Zoom:", page))
        self.zoom_spin = QDoubleSpinBox(page)
        self.zoom_spin.setRange(10.0, 4000.0)
        self.zoom_spin.setSuffix(" %")
        self.zoom_spin.setSingleStep(10.0)
        self.zoom_spin.setValue(100.0)
        self.zoom_spin.valueChanged.connect(self._on_zoom_changed)
        row.addWidget(self.zoom_spin)

        row.addWidget(QLabel("View:", page))
        self.view_mode_combo = QComboBox(page)
        self.view_mode_combo.addItems(["paged", "flow"])
        self.view_mode_combo.currentTextChanged.connect(self._on_view_mode_changed)
        row.addWidget(self.view_mode_combo)
        row.addStretch(1)
        return page

    def _build_geometry_mode(self) -> QWidget:
        page = QWidget(self)
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.x_spin = self._make_pt_spin(page)
        self.y_spin = self._make_pt_spin(page)
        self.w_spin = self._make_pt_spin(page, minimum=0.0)
        self.h_spin = self._make_pt_spin(page, minimum=0.0)
        self.rotation_spin = self._make_pt_spin(page, minimum=-360.0, maximum=360.0, suffix="°")
        self.skew_spin = self._make_pt_spin(page, minimum=-89.0, maximum=89.0, suffix="°")

        for label, spin, slot in (
            ("X:", self.x_spin, self._on_x_changed),
            ("Y:", self.y_spin, self._on_y_changed),
            ("W:", self.w_spin, self._on_w_changed),
            ("H:", self.h_spin, self._on_h_changed),
            ("∠:", self.rotation_spin, self._on_rotation_changed),
            ("Skew:", self.skew_spin, self._on_skew_changed),
        ):
            row.addWidget(QLabel(label, page))
            spin.valueChanged.connect(slot)
            row.addWidget(spin)

        self.aspect_lock = QToolButton(page)
        self.aspect_lock.setCheckable(True)
        self.aspect_lock.setText("⇆⇅")
        self.aspect_lock.setToolTip("Lock aspect ratio")
        self.aspect_lock.toggled.connect(self._on_aspect_lock_toggled)
        row.addWidget(self.aspect_lock)
        row.addStretch(1)
        return page

    def _build_text_mode(self) -> QWidget:
        page = QWidget(self)
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.font_combo = QFontComboBox(page)
        self.font_combo.currentFontChanged.connect(self._on_font_changed)
        row.addWidget(self.font_combo)

        self.size_spin = self._make_pt_spin(page, minimum=1.0, maximum=1296.0)
        self.size_spin.valueChanged.connect(self._on_size_changed)
        row.addWidget(QLabel("Size:", page))
        row.addWidget(self.size_spin)

        self.leading_spin = self._make_pt_spin(page, minimum=0.0, maximum=1296.0)
        self.leading_spin.valueChanged.connect(self._on_leading_changed)
        row.addWidget(QLabel("Leading:", page))
        row.addWidget(self.leading_spin)

        self.tracking_spin = self._make_pt_spin(page, minimum=-1000.0, maximum=10000.0)
        self.tracking_spin.valueChanged.connect(self._on_tracking_changed)
        row.addWidget(QLabel("Tracking:", page))
        row.addWidget(self.tracking_spin)

        self.alignment_group = QButtonGroup(page)
        self.alignment_group.setExclusive(True)
        for token, glyph in (
            ("left", "⯇"),
            ("center", "≡"),
            ("right", "⯈"),
            ("justify", "☰"),
        ):
            btn = QToolButton(page)
            btn.setText(glyph)
            btn.setCheckable(True)
            btn.setToolTip(f"Align {token}")
            btn.setProperty("alignment_token", token)
            self.alignment_group.addButton(btn)
            row.addWidget(btn)
        self.alignment_group.buttonToggled.connect(self._on_alignment_toggled)

        self.bold_btn = QToolButton(page)
        self.bold_btn.setText("B")
        f = self.bold_btn.font()
        f.setBold(True)
        self.bold_btn.setFont(f)
        self.bold_btn.setCheckable(True)
        self.bold_btn.toggled.connect(self._on_bold_toggled)
        row.addWidget(self.bold_btn)

        self.italic_btn = QToolButton(page)
        self.italic_btn.setText("I")
        fi = self.italic_btn.font()
        fi.setItalic(True)
        self.italic_btn.setFont(fi)
        self.italic_btn.setCheckable(True)
        self.italic_btn.toggled.connect(self._on_italic_toggled)
        row.addWidget(self.italic_btn)

        self.underline_btn = QToolButton(page)
        self.underline_btn.setText("U")
        fu = self.underline_btn.font()
        fu.setUnderline(True)
        self.underline_btn.setFont(fu)
        self.underline_btn.setCheckable(True)
        self.underline_btn.toggled.connect(self._on_underline_toggled)
        row.addWidget(self.underline_btn)

        self.strike_btn = QToolButton(page)
        self.strike_btn.setText("S")
        fs = self.strike_btn.font()
        fs.setStrikeOut(True)
        self.strike_btn.setFont(fs)
        self.strike_btn.setCheckable(True)
        self.strike_btn.toggled.connect(self._on_strike_toggled)
        row.addWidget(self.strike_btn)

        self.paragraph_style_combo = QComboBox(page)
        # paragraph_styles may be a dict (unit-8) or a list of styles (master).
        styles = self._document.paragraph_styles
        if isinstance(styles, dict):
            self.paragraph_style_combo.addItems(list(styles.keys()))
        else:
            self.paragraph_style_combo.addItems(
                [getattr(s, "name", str(s)) for s in styles]
            )
        self.paragraph_style_combo.currentTextChanged.connect(self._on_paragraph_style_changed)
        row.addWidget(QLabel("Style:", page))
        row.addWidget(self.paragraph_style_combo)

        self.opentype_btn = QPushButton("OT…", page)
        self.opentype_btn.setToolTip("OpenType features")
        self._opentype_menu = QMenu(self.opentype_btn)
        self._opentype_actions: dict[str, QAction] = {}
        for tag, label in _OT_FEATURES:
            action = self._opentype_menu.addAction(f"{tag}  {label}")
            action.setCheckable(True)
            action.setData(tag)
            action.toggled.connect(
                lambda checked, t=tag: self._on_opentype_toggled(t, checked)
            )
            self._opentype_actions[tag] = action
        self.opentype_btn.setMenu(self._opentype_menu)
        row.addWidget(self.opentype_btn)

        row.addStretch(1)
        return page

    def _build_columns_mode(self) -> QWidget:
        page = QWidget(self)
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.columns_spin = QSpinBox(page)
        self.columns_spin.setRange(1, 32)
        self.columns_spin.valueChanged.connect(self._on_columns_changed)
        row.addWidget(QLabel("Cols:", page))
        row.addWidget(self.columns_spin)

        self.gutter_spin = self._make_pt_spin(page, minimum=0.0, maximum=720.0)
        self.gutter_spin.valueChanged.connect(self._on_gutter_changed)
        row.addWidget(QLabel("Gutter:", page))
        row.addWidget(self.gutter_spin)

        self.baseline_grid_check = QCheckBox("Baseline grid", page)
        self.baseline_grid_check.toggled.connect(self._on_baseline_grid_toggled)
        row.addWidget(self.baseline_grid_check)

        self.vertical_align_combo = QComboBox(page)
        self.vertical_align_combo.addItems(["top", "center", "bottom", "justify"])
        self.vertical_align_combo.currentTextChanged.connect(self._on_vertical_align_changed)
        row.addWidget(QLabel("V-align:", page))
        row.addWidget(self.vertical_align_combo)

        row.addStretch(1)
        return page

    @staticmethod
    def _make_pt_spin(
        parent: QWidget,
        *,
        minimum: float = -100000.0,
        maximum: float = 100000.0,
        suffix: str = " pt",
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(parent)
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(1.0)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        spin.setSpecialValueText("")
        return spin

    # ------------------------------------------------------------------ mode selection

    def current_mode(self) -> int:
        return self._stack.currentIndex()

    def _refresh(self) -> None:
        # Defensive: master's Document doesn't carry .selection yet (unit-22 +
        # downstream wiring will). Treat absent selection as empty.
        from msword.model.selection import Selection

        sel = getattr(self._document, "selection", None) or Selection()
        if sel.has_caret:
            self._stack.setCurrentIndex(_MODE_TEXT)
            self._populate_text_mode()
        elif sel.is_empty:
            self._stack.setCurrentIndex(_MODE_EMPTY)
            self._populate_empty_mode()
        elif sel.is_multi_frame:
            self._stack.setCurrentIndex(_MODE_GEOMETRY)
            self._populate_geometry_mode_mixed()
        elif sel.single_text_frame is not None:
            self._stack.setCurrentIndex(_MODE_COLUMNS)
            self._populate_columns_mode(sel.single_text_frame)
        elif sel.single_frame is not None:
            self._stack.setCurrentIndex(_MODE_GEOMETRY)
            self._populate_geometry_mode(sel.single_frame)
        else:
            self._stack.setCurrentIndex(_MODE_EMPTY)
            self._populate_empty_mode()

    # ------------------------------------------------------------------ populate

    def _populate_empty_mode(self) -> None:
        with self._suspended():
            self.zoom_spin.setValue(self._document.zoom * 100.0)
            idx = self.view_mode_combo.findText(self._document.view_mode)
            if idx >= 0:
                self.view_mode_combo.setCurrentIndex(idx)

    def _populate_geometry_mode(self, frame: Frame) -> None:
        with self._suspended():
            for spin, value in (
                (self.x_spin, frame.x),
                (self.y_spin, frame.y),
                (self.w_spin, frame.w),
                (self.h_spin, frame.h),
                (self.rotation_spin, frame.rotation),
                (self.skew_spin, frame.skew),
            ):
                spin.setSpecialValueText("")
                spin.setValue(value)
            self.aspect_lock.setChecked(frame.aspect_locked)

    def _populate_geometry_mode_mixed(self) -> None:
        with self._suspended():
            for spin in (
                self.x_spin,
                self.y_spin,
                self.w_spin,
                self.h_spin,
                self.rotation_spin,
                self.skew_spin,
            ):
                spin.setSpecialValueText(MIXED_PLACEHOLDER)
                spin.setValue(spin.minimum())
            self.aspect_lock.setChecked(False)

    def _populate_text_mode(self) -> None:
        run = self._document.selection.caret_run
        if run is None:
            return
        with self._suspended():
            self.font_combo.setCurrentFont(QFont(run.font_family))
            self.size_spin.setValue(run.size)
            self.leading_spin.setValue(run.leading)
            self.tracking_spin.setValue(run.tracking)
            for btn in self.alignment_group.buttons():
                btn.setChecked(btn.property("alignment_token") == run.alignment)
            self.bold_btn.setChecked(run.bold)
            self.italic_btn.setChecked(run.italic)
            self.underline_btn.setChecked(run.underline)
            self.strike_btn.setChecked(run.strike)
            idx = self.paragraph_style_combo.findText(run.paragraph_style_ref)
            if idx >= 0:
                self.paragraph_style_combo.setCurrentIndex(idx)
            for tag, action in self._opentype_actions.items():
                action.setChecked(tag in run.opentype_features)

    def _populate_columns_mode(self, frame: TextFrame) -> None:
        with self._suspended():
            self.columns_spin.setValue(frame.columns)
            self.gutter_spin.setValue(frame.gutter)
            self.baseline_grid_check.setChecked(frame.baseline_grid)
            idx = self.vertical_align_combo.findText(frame.vertical_align)
            if idx >= 0:
                self.vertical_align_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------ slots — empty

    def _on_zoom_changed(self, value: float) -> None:
        if self._suspend_signals:
            return
        self._schedule(SetZoomCommand(zoom=value / 100.0))

    def _on_view_mode_changed(self, mode: str) -> None:
        if self._suspend_signals or not mode:
            return
        self._schedule(SetViewModeCommand(view_mode=mode))

    # ------------------------------------------------------------------ slots — geometry

    def _selected_frame(self) -> Frame | None:
        """Single frame currently being edited, or `None` if signals should be ignored."""
        if self._suspend_signals:
            return None
        frame: Frame | None = self._document.selection.single_frame
        return frame

    def _on_x_changed(self, value: float) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(MoveFrameCommand(frame_id=f.id, x=value, y=f.y))

    def _on_y_changed(self, value: float) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(MoveFrameCommand(frame_id=f.id, x=f.x, y=value))

    def _on_w_changed(self, value: float) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(ResizeFrameCommand(frame_id=f.id, w=value, h=f.h))

    def _on_h_changed(self, value: float) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(ResizeFrameCommand(frame_id=f.id, w=f.w, h=value))

    def _on_rotation_changed(self, value: float) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(RotateFrameCommand(frame_id=f.id, rotation=value))

    def _on_skew_changed(self, value: float) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(SkewFrameCommand(frame_id=f.id, skew=value))

    def _on_aspect_lock_toggled(self, checked: bool) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(SetAspectLockCommand(frame_id=f.id, locked=checked))

    # ------------------------------------------------------------------ slots — text

    def _on_font_changed(self, font: QFont) -> None:
        if self._suspend_signals:
            return
        self._schedule(SetFontCommand(family=font.family()))

    def _on_size_changed(self, value: float) -> None:
        if self._suspend_signals:
            return
        self._schedule(SetSizeCommand(size=value))

    def _on_leading_changed(self, value: float) -> None:
        if self._suspend_signals:
            return
        self._schedule(SetLeadingCommand(leading=value))

    def _on_tracking_changed(self, value: float) -> None:
        if self._suspend_signals:
            return
        self._schedule(SetTrackingCommand(tracking=value))

    def _on_alignment_toggled(self, button: QAbstractButton, checked: bool) -> None:
        if self._suspend_signals or not checked:
            return
        token = button.property("alignment_token")
        if not isinstance(token, str):
            return
        self._schedule(SetAlignmentCommand(alignment=token))

    def _on_bold_toggled(self, checked: bool) -> None:
        if self._suspend_signals:
            return
        self._push_now(SetBoldCommand(bold=checked))

    def _on_italic_toggled(self, checked: bool) -> None:
        if self._suspend_signals:
            return
        self._push_now(SetItalicCommand(italic=checked))

    def _on_underline_toggled(self, checked: bool) -> None:
        if self._suspend_signals:
            return
        self._push_now(SetUnderlineCommand(underline=checked))

    def _on_strike_toggled(self, checked: bool) -> None:
        if self._suspend_signals:
            return
        self._push_now(SetStrikeCommand(strike=checked))

    def _on_paragraph_style_changed(self, name: str) -> None:
        if self._suspend_signals or not name:
            return
        self._schedule(SetParagraphStyleCommand(style_name=name))

    def _on_opentype_toggled(self, tag: str, enabled: bool) -> None:
        if self._suspend_signals:
            return
        self._push_now(SetOpenTypeFeatureCommand(feature=tag, enabled=enabled))

    # ------------------------------------------------------------------ slots — columns

    def _on_columns_changed(self, value: int) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(SetColumnsCommand(frame_id=f.id, columns=value))

    def _on_gutter_changed(self, value: float) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(SetGutterCommand(frame_id=f.id, gutter=value))

    def _on_baseline_grid_toggled(self, checked: bool) -> None:
        f = self._selected_frame()
        if f is None:
            return
        self._push_now(SetBaselineGridCommand(frame_id=f.id, enabled=checked))

    def _on_vertical_align_changed(self, mode: str) -> None:
        if not mode:
            return
        f = self._selected_frame()
        if f is None:
            return
        self._schedule(SetVerticalAlignCommand(frame_id=f.id, vertical_align=mode))

    # ------------------------------------------------------------------ debounce

    def _schedule(self, command: Any) -> None:
        """Coalesce a stream of edits into a single push after `DEBOUNCE_MS`."""
        self._pending_command = command
        self._debounce.start()

    def _flush_pending(self) -> None:
        cmd = self._pending_command
        self._pending_command = None
        if cmd is not None:
            self._document.undo_stack.push(cmd)

    def _push_now(self, command: Any) -> None:
        self._document.undo_stack.push(command)

    # ------------------------------------------------------------------ helpers

    def _suspended(self) -> _Suspend:
        return _Suspend(self)


class _Suspend:
    """Context manager that disables signal-driven command pushes during refresh."""

    def __init__(self, palette: MeasurementsPalette) -> None:
        self._palette = palette

    def __enter__(self) -> MeasurementsPalette:
        self._palette._suspend_signals = True
        return self._palette

    def __exit__(self, *exc: object) -> None:
        self._palette._suspend_signals = False


__all__ = ["DEBOUNCE_MS", "MIXED_PLACEHOLDER", "MeasurementsPalette"]
